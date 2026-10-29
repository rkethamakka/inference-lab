import json

import httpx
import pytest

from lab import bench, cli, manifest, serve
from tests import mock_server


@pytest.fixture
def m():
    return manifest.load()


def test_manifest_loads_and_hash_is_stable(m):
    assert m.model["id"]
    assert m.hash() == manifest.load().hash()
    assert len(m.hash()) == 12


def test_strict_mode_rejects_unpinned(tmp_path):
    path = tmp_path / "m.yaml"
    path.write_text(manifest.DEFAULT_PATH.read_text())
    if manifest.load(path).unpinned():
        with pytest.raises(manifest.ManifestError):
            manifest.load(path, strict=True)


def test_missing_platform_key_is_an_error(tmp_path):
    path = tmp_path / "m.yaml"
    path.write_text("model: {id: x}\nplatforms:\n  cuda: {instance_type: g6}\n  neuron: {}\n")
    with pytest.raises(manifest.ManifestError):
        manifest.load(path)


def test_serve_command_per_platform(m):
    cuda = serve.build_command(m, "cuda")
    neuron = serve.build_command(m, "neuron")
    assert cuda[:3] == ["vllm", "serve", m.model["id"]]
    assert "--device" not in cuda
    assert neuron[-2:] == ["--device", "neuron"]
    assert "--tensor-parallel-size" in neuron


def test_neuron_cache_is_keyed_by_manifest_hash(m):
    env = serve.build_env(m, "neuron", cache_root="/mnt/cache")
    assert env[serve.NEURON_CACHE_ENV].endswith(m.hash())
    assert serve.build_env(m, "cuda", cache_root="/mnt/cache") == {}


def test_smoke_against_mock_server():
    server, url = mock_server.start()
    try:
        assert httpx.get(f"{url}/health").status_code == 200
        record = bench.run(url, "mock", "cuda", "abc", concurrency_levels=(1, 4), requests_per_level=8)
    finally:
        server.shutdown()
    assert [lv.concurrency for lv in record.levels] == [1, 4]
    for lv in record.levels:
        assert lv.errors == 0
        assert lv.tokens_per_s > 0
        assert lv.ttft_p95_ms >= lv.ttft_p50_ms
    assert json.loads(record.to_json())["manifest_hash"] == "abc"


def test_percentile():
    assert bench.percentile([], 95) == 0.0
    assert bench.percentile([1, 2, 3, 4, 5], 50) == 3


def test_cli_check(capsys):
    assert cli.main(["check"]) == 0
    assert "manifest ok" in capsys.readouterr().out
