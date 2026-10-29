# TDD: Inference Lab

Status: Draft · Owner: Ravi Kiran · Last updated: 2026-10-28 · Requirements: [PRD](PRD.md)

## 1. Overview

A monorepo with four parts:

1. **serving/** — one server entrypoint that runs vLLM with either the CUDA or Neuron backend and exposes the OpenAI-compatible API.
2. **toolchains/** — a version manifest per platform and the container images built from it.
3. **infra/** — Terraform for the AWS account: VPC, devbox templates, CI runner launch, S3 caches, budget alarms.
4. **ci/** and **metrics/** — GitHub Actions workflows, the benchmark harness, and the pipeline that turns CI and benchmark results into a dashboard.

```
developer ──PR──▶ GitHub Actions
                    ├─ pre-land (GitHub-hosted, CPU): lint, unit, mock smoke
                    └─ hardware (label / main / nightly)
                          ├─ start ephemeral runner ──▶ g6.xlarge (L4, CUDA)
                          └─ start ephemeral runner ──▶ inf2.xlarge (Inferentia2, Neuron)
                                 └─ pull image from ECR ─ load model ─ smoke ─ benchmark ─ teardown
                    results (JSON) ──▶ S3 ──▶ metrics pipeline ──▶ dashboard + alerts
```

## 2. Hardware

| Platform | Instance | Accelerator | Approx. on-demand cost |
|---|---|---|---|
| CUDA | g6.xlarge | 1× NVIDIA L4, 24 GB | about $0.80/hr |
| Neuron | inf2.xlarge | 1× Inferentia2, 32 GB | about $0.76/hr |
| Neuron (optional) | trn1.2xlarge | 1× Trainium, 32 GB | about $1.34/hr |

Check current prices and quotas before M1. A 7–8B model in BF16 fits on one device for each instance.

## 3. Toolchain manifest (`toolchains/manifest.yaml`)

```yaml
model:
  id: Qwen/Qwen2.5-7B-Instruct        # must be on the Neuron supported-model list
  max_model_len: 4096
platforms:
  cuda:
    base_image: nvidia/cuda:<pinned>-runtime-ubuntu22.04
    driver_min: "<pinned>"
    torch: "<pinned>"
    vllm: "<pinned>"
  neuron:
    base_image: <AWS Neuron DLC, pinned>
    neuron_sdk: "<pinned>"             # neuronx-cc, torch-neuronx, NxD Inference
    vllm: "<pinned, Neuron build>"
```

- Exact versions are filled in at M1/M2 from the current compatibility tables, not guessed.
- `make images` builds one image per platform, tagged with the manifest hash, and pushes it to ECR.
- A change to the manifest is the only way to change a toolchain version. CI rejects images whose versions don't match it.

## 4. Serving (`serving/`)

- `serve.py --platform {cuda,neuron}` starts vLLM with the right backend and settings from the manifest.
- Same API on both platforms: `/v1/chat/completions`, `/health`, `/metrics`.
- Neuron needs ahead-of-time compilation. Compiled artifacts are stored in `s3://<bucket>/neuron-cache/<model>/<manifest-hash>/` and reused, so only a toolchain or model change pays the compile cost.

## 5. Devboxes (`infra/devbox`, `bin/lab`)

- `lab devbox up --platform cuda|neuron` launches an EC2 instance from a launch template using the platform image, mounts the S3 caches, and prints an SSH or VS Code Remote command.
- `lab devbox down` terminates it. A cron on the box shuts it down after 60 minutes with no SSH session and no accelerator utilization.
- Every devbox is tagged with owner and expiry; a scheduled Lambda terminates anything past expiry.
- Time-to-ready is measured and emitted as a metric.

## 6. CI (`.github/workflows/`)

| Workflow | Trigger | Runs on | Steps | Budget |
|---|---|---|---|---|
| `pre-land.yml` | every PR | GitHub-hosted | ruff, mypy, pytest, CPU mock smoke against a tiny model | under 10 min |
| `hardware.yml` | PR label `run-hw`, push to main, nightly | ephemeral EC2 self-hosted runners, one per platform | pull image, load model (warm cache), smoke test, benchmark, upload results, terminate | 45 min hard timeout |
| `canary.yml` | nightly | ephemeral runners | bump manifest to newest releases on a branch, build images, run hardware suite, open a PR if green, file an issue if red | 90 min hard timeout |

Ephemeral runners: a job first calls the AWS API (OIDC role, no long-lived keys) to start an instance that registers itself as a single-use GitHub runner, and an `always()` step terminates it. Evaluate an existing action (for example `ec2-github-runner`) before building one; record the build vs. adopt decision as an ADR.

## 7. Smoke tests and benchmark (`bench/`)

- **Smoke:** server starts, `/health` returns OK, a fixed prompt returns a non-empty answer, and a greedy-decoded output matches a stored golden answer within a similarity threshold.
- **Benchmark:** fixed prompt set, concurrency levels 1, 4 and 16; records time to first token (p50/p95), inter-token latency, output tokens per second, and cost per million tokens.
- **Regression check:** compare against the last green main run on the same platform; flag changes over 5% on the PR as a comment.

## 8. Metrics and dashboard (`metrics/`)

Every CI job and benchmark writes a JSON record to S3:

```json
{"run_id": "...", "workflow": "hardware", "platform": "neuron", "git_sha": "...",
 "manifest_hash": "...", "status": "success", "queued_s": 40, "duration_s": 1260,
 "compile_cache_hit": true, "ttft_p50_ms": 0, "ttft_p95_ms": 0,
 "tokens_per_s": 0, "cost_usd": 0.41}
```

- Records are loaded into Grafana Cloud (free tier) or DuckDB plus a static dashboard on GitHub Pages; pick one in an ADR at M5.
- Panels: pre-land and hardware CI duration (p50/p95), main health by platform, hours red, time-to-green, canary age (days behind latest toolchain), devbox time-to-ready, benchmark trends, spend.

## 9. SLOs and alerts

| SLO | Objective | Alert |
|---|---|---|
| Pre-land CI duration | p50 under 10 min over 7 days | p50 above 12 min |
| Main hardware health | green at least 95% of days | red for more than 24 hours |
| Toolchain freshness | pinned within 7 days of newest compatible release | canary red for 3 nights in a row |
| Performance | no unflagged regression over 5% | regression merged to main |
| Cost | under $150/month | AWS Budgets at 50%, 80%, 100% |

Alerts go to email or a GitHub issue to start with.

## 10. Security and cost

- GitHub to AWS via OIDC; no stored access keys.
- Hugging Face token in AWS Secrets Manager, fetched at runtime.
- Every instance has a hard maximum lifetime and owner tags. The budget alarm is created before any GPU or Inferentia instance is launched.

## 11. Planned ADRs

1. Ephemeral runner: build vs. adopt an existing action.
2. Metrics store: Grafana Cloud vs. DuckDB with a static site.
3. Model choice, after checking the Neuron supported-model list.
4. Spot vs. on-demand for CI runners.
