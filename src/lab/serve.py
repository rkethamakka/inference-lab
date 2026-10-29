"""Build the vLLM server command for a platform from the manifest.

The same OpenAI-compatible API is exposed on every platform; only backend flags differ.
Neuron flags must be re-checked against the pinned Neuron SDK release at M2.
"""

from __future__ import annotations

import os
import shlex

from lab.manifest import Manifest

NEURON_CACHE_ENV = "NEURON_COMPILED_ARTIFACTS"


def build_command(manifest: Manifest, platform: str, port: int = 8000) -> list[str]:
    model = manifest.model
    section = manifest.platform(platform)
    cmd = [
        "vllm", "serve", model["id"],
        "--port", str(port),
        "--max-model-len", str(model.get("max_model_len", 4096)),
        "--dtype", model.get("dtype", "auto"),
    ]
    for key, value in sorted(section.get("serve_args", {}).items()):
        cmd += [f"--{key.replace('_', '-')}", str(value)]
    if platform == "neuron":
        cmd += ["--device", "neuron"]
    return cmd


def build_env(manifest: Manifest, platform: str, cache_root: str | None = None) -> dict[str, str]:
    """Extra environment for the server. Neuron reuses compiled artifacts keyed by manifest hash."""
    env: dict[str, str] = {}
    if platform == "neuron" and cache_root:
        model_slug = manifest.model["id"].replace("/", "--")
        env[NEURON_CACHE_ENV] = os.path.join(cache_root, model_slug, manifest.hash())
    return env


def render(manifest: Manifest, platform: str, port: int = 8000, cache_root: str | None = None) -> str:
    env = build_env(manifest, platform, cache_root)
    prefix = " ".join(f"{k}={shlex.quote(v)}" for k, v in env.items())
    cmd = shlex.join(build_command(manifest, platform, port))
    return f"{prefix} {cmd}".strip()
