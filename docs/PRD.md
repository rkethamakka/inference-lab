# PRD: Inference Lab

Status: Draft · Owner: Ravi Kiran · Last updated: 2026-10-28

## 1. Problem

Inference teams ship software that must work on several accelerator stacks at once: NVIDIA GPUs (CUDA), AWS Inferentia/Trainium (Neuron) and TPUs. Each stack has its own drivers, compilers, libraries and framework versions. Engineers lose time to environment problems instead of model serving work:

- Toolchain versions drift, and a driver or compiler bump breaks one platform silently.
- Getting a working dev box on scarce hardware is slow and expensive.
- Hardware tests run late (or not at all), so regressions land on main and stay red.
- Nobody can say whether developer velocity is getting better or worse, because nothing is measured.

## 2. Goal

Build a small but real developer-productivity platform for multi-accelerator inference, and use it to serve one open model on two hardware stacks with the same API. The platform, not the model, is the product.

Personal goal: gain hands-on CUDA and AWS Neuron toolchain experience, plus measured developer-workflow metrics, that can be shown in interviews and on a resume.

## 3. Users

- **Inference engineer** (primary): changes serving code and wants fast, trustworthy feedback on every platform.
- **Platform owner** (me): keeps toolchains current, watches health metrics, decides build vs. adopt.

## 4. Scope

### In scope (v1)

| # | Capability | What "done" means |
|---|---|---|
| R1 | Same model, two stacks | One open model (default Qwen2.5-7B-Instruct or Llama 3.1 8B) served through an OpenAI-compatible API on an NVIDIA GPU (vLLM, CUDA) and on AWS Inferentia2 (vLLM with the Neuron backend) |
| R2 | Pinned toolchains | One manifest pins driver, compiler, library and framework versions per platform; container images are built from it |
| R3 | Compatibility tests | Each toolchain bump runs a test matrix and reports pass or fail per platform |
| R4 | Ephemeral devboxes | One command starts a dev box on the chosen hardware with the toolchain installed; it stops itself when idle |
| R5 | Pre-land CI | Every PR runs lint, unit tests and a CPU smoke test in under 10 minutes |
| R6 | Hardware CI | A PR label, merges to main and a nightly job start ephemeral GPU and Inferentia runners, run smoke tests and a benchmark, then tear the hardware down |
| R7 | Toolchain canary | A nightly job tries the newest vLLM, CUDA and Neuron SDK versions and opens a PR when they pass |
| R8 | Velocity metrics | A dashboard shows CI duration, main-branch health, time-to-green, benchmark throughput and latency, and cost per run |
| R9 | SLOs and alerts | Written SLOs on developer workflows, with alerts when they are breached |
| R10 | Cost guardrails | Monthly budget alarm, maximum runtime on every hardware job, automatic teardown |

### Out of scope (v1)

- TPU support (no low-cost access; designed for, not built)
- Multi-node or tensor-parallel serving across machines
- Production-grade autoscaling or multi-tenant serving
- Custom kernels (Triton, NKI) — a v2 stretch goal

## 5. Success metrics

| Metric | Target |
|---|---|
| Pre-land CI duration (p50) | Under 10 minutes |
| Hardware CI duration, smoke + benchmark (p50) | Under 30 minutes per platform |
| Main-branch hardware smoke health | Green on at least 95% of days; never red more than 24 hours |
| Time from toolchain release to pinned upgrade | Under 7 days, via the canary PR |
| Devbox time-to-ready | Under 10 minutes from command to a working shell |
| Benchmark regression detection | Any throughput or p95 latency change over 5% is flagged on the PR |
| Monthly cloud spend | Under $150 |

## 6. Milestones

| Milestone | Content | Target |
|---|---|---|
| M0 | Repo, PRD, TDD, AWS account ready (quotas approved) | Week 1 |
| M1 | Model served on an NVIDIA GPU devbox, benchmark script | Week 2 |
| M2 | Same model served on Inferentia2, same API and benchmark | Week 3 |
| M3 | Pre-land CI plus ephemeral hardware runners | Week 4 |
| M4 | Toolchain manifest, compatibility matrix, nightly canary | Week 5 |
| M5 | Metrics pipeline, dashboard, SLOs and alerts | Week 6 |
| M6 | Write-up: results, lessons, numbers for the resume | Week 7 |

## 7. Risks

| Risk | Mitigation |
|---|---|
| New AWS accounts have zero GPU and Inferentia quota | Request G and Inf quota increases in week 1, before anything else |
| Neuron compilation is slow (tens of minutes) | Cache compiled artifacts in S3, keyed by model and toolchain version |
| Cost overrun from forgotten instances | Idle auto-stop, hard maximum runtime, AWS Budgets alarm |
| Spot capacity unavailable | Fall back to on-demand for CI; keep runs short |
| Model or toolchain not supported on Neuron | Pick a model on the Neuron supported-model list |

## 8. Open questions

1. Which AWS account and region? (Default: a personal account in us-east-1 or us-west-2, wherever g6 and inf2 capacity is best.)
2. Monthly budget ceiling. (Default: $150.)
3. Public or private repo? (Default: private while building, public at M6 so it can be linked from the resume.)
