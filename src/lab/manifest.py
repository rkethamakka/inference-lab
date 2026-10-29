"""Load and validate toolchains/manifest.yaml."""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import yaml

PLATFORMS = ("cuda", "neuron")
UNPINNED = "unpinned"
REQUIRED_KEYS = {
    "cuda": ("instance_type", "base_image", "driver_min", "torch", "vllm"),
    "neuron": ("instance_type", "base_image", "neuron_sdk", "vllm"),
}
DEFAULT_PATH = Path(__file__).resolve().parents[2] / "toolchains" / "manifest.yaml"


class ManifestError(ValueError):
    pass


@dataclass(frozen=True)
class Manifest:
    raw: dict[str, Any]

    @property
    def model(self) -> dict[str, Any]:
        return self.raw["model"]

    def platform(self, name: str) -> dict[str, Any]:
        if name not in PLATFORMS:
            raise ManifestError(f"unknown platform {name!r}; expected one of {PLATFORMS}")
        return self.raw["platforms"][name]

    def hash(self) -> str:
        """Stable short hash, used to tag images and key the Neuron compile cache."""
        canonical = json.dumps(self.raw, sort_keys=True, separators=(",", ":"))
        return hashlib.sha256(canonical.encode()).hexdigest()[:12]

    def unpinned(self) -> list[str]:
        return [
            f"{p}.{k}"
            for p in PLATFORMS
            for k in REQUIRED_KEYS[p]
            if str(self.raw["platforms"][p].get(k)) == UNPINNED
        ]


def load(path: Path | str = DEFAULT_PATH, strict: bool = False) -> Manifest:
    raw = yaml.safe_load(Path(path).read_text())
    if not isinstance(raw, dict) or "model" not in raw or "platforms" not in raw:
        raise ManifestError("manifest needs top-level 'model' and 'platforms'")
    if "id" not in raw["model"]:
        raise ManifestError("model.id is required")
    for p in PLATFORMS:
        section = raw["platforms"].get(p)
        if not isinstance(section, dict):
            raise ManifestError(f"platforms.{p} is missing")
        missing = [k for k in REQUIRED_KEYS[p] if k not in section]
        if missing:
            raise ManifestError(f"platforms.{p} is missing {missing}")
    manifest = Manifest(raw)
    if strict and manifest.unpinned():
        raise ManifestError(f"unpinned toolchain versions: {manifest.unpinned()}")
    return manifest
