# Inference Lab

A developer-productivity platform for multi-accelerator LLM inference: one open model served with the same API on NVIDIA GPUs (CUDA) and AWS Inferentia2 (Neuron), with pinned toolchains, ephemeral devboxes, hardware CI, a nightly toolchain canary, and dashboards and SLOs on developer workflows.

- [PRD](docs/PRD.md): problem, scope, success metrics, milestones
- [TDD](docs/TDD.md): architecture, toolchains, CI, metrics, SLOs

Status: M1 scaffolding (no hardware yet).

## Quick start

```bash
python3 -m venv .venv && .venv/bin/pip install -e ".[dev]"
.venv/bin/lab check                          # validate toolchains/manifest.yaml
.venv/bin/lab serve-cmd --platform cuda      # print the vLLM command for a platform
.venv/bin/lab bench --platform cuda --url http://localhost:8000   # benchmark a running server
.venv/bin/pytest -q                          # unit tests + CPU smoke test against a mock server
```

## Layout

- `toolchains/manifest.yaml`: the only place toolchain versions are set
- `src/lab/`: manifest loader, server command builder, benchmark harness, `lab` CLI
- `tests/`: unit tests and a mock OpenAI-compatible server for CPU smoke tests
- `.github/workflows/pre-land.yml`: lint, manifest check and tests on every PR
