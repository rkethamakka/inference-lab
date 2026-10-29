"""Benchmark an OpenAI-compatible endpoint and emit a result record (TDD section 8)."""

from __future__ import annotations

import asyncio
import json
import statistics
import time
from dataclasses import asdict, dataclass, field

import httpx

DEFAULT_PROMPTS = [
    "Explain what a compiler does in two sentences.",
    "List three uses of a hash map.",
    "Summarize the CAP theorem in one paragraph.",
    "Write a haiku about continuous integration.",
]


@dataclass
class RequestResult:
    ttft_s: float
    total_s: float
    output_tokens: int


@dataclass
class LevelResult:
    concurrency: int
    requests: int
    ttft_p50_ms: float
    ttft_p95_ms: float
    tokens_per_s: float
    errors: int = 0


@dataclass
class BenchRecord:
    platform: str
    model: str
    manifest_hash: str
    levels: list[LevelResult] = field(default_factory=list)

    def to_json(self) -> str:
        return json.dumps(asdict(self), indent=2)


def percentile(values: list[float], pct: float) -> float:
    if not values:
        return 0.0
    ordered = sorted(values)
    idx = min(len(ordered) - 1, max(0, round(pct / 100 * (len(ordered) - 1))))
    return ordered[idx]


async def one_request(
    client: httpx.AsyncClient, model: str, prompt: str, max_tokens: int
) -> RequestResult:
    body = {
        "model": model,
        "messages": [{"role": "user", "content": prompt}],
        "max_tokens": max_tokens,
        "temperature": 0,
        "stream": True,
    }
    start = time.perf_counter()
    ttft = None
    tokens = 0
    async with client.stream("POST", "/v1/chat/completions", json=body) as resp:
        resp.raise_for_status()
        async for line in resp.aiter_lines():
            if not line.startswith("data: ") or line == "data: [DONE]":
                continue
            delta = json.loads(line[6:])["choices"][0].get("delta", {}).get("content")
            if delta:
                if ttft is None:
                    ttft = time.perf_counter() - start
                tokens += 1  # one streamed chunk is roughly one token in vLLM
    total = time.perf_counter() - start
    return RequestResult(ttft_s=ttft if ttft is not None else total, total_s=total, output_tokens=tokens)


async def run_level(
    base_url: str, model: str, concurrency: int, requests: int, max_tokens: int
) -> LevelResult:
    sem = asyncio.Semaphore(concurrency)
    results: list[RequestResult] = []
    errors = 0

    async with httpx.AsyncClient(base_url=base_url, timeout=300) as client:

        async def worker(i: int) -> None:
            nonlocal errors
            async with sem:
                try:
                    prompt = DEFAULT_PROMPTS[i % len(DEFAULT_PROMPTS)]
                    results.append(await one_request(client, model, prompt, max_tokens))
                except httpx.HTTPError:
                    errors += 1

        wall_start = time.perf_counter()
        await asyncio.gather(*(worker(i) for i in range(requests)))
        wall = time.perf_counter() - wall_start

    ttfts = [r.ttft_s * 1000 for r in results]
    return LevelResult(
        concurrency=concurrency,
        requests=requests,
        ttft_p50_ms=round(statistics.median(ttfts), 2) if ttfts else 0.0,
        ttft_p95_ms=round(percentile(ttfts, 95), 2),
        tokens_per_s=round(sum(r.output_tokens for r in results) / wall, 2) if wall else 0.0,
        errors=errors,
    )


def run(
    base_url: str,
    model: str,
    platform: str,
    manifest_hash: str,
    concurrency_levels: tuple[int, ...] = (1, 4, 16),
    requests_per_level: int = 16,
    max_tokens: int = 128,
) -> BenchRecord:
    record = BenchRecord(platform=platform, model=model, manifest_hash=manifest_hash)
    for c in concurrency_levels:
        level = asyncio.run(run_level(base_url, model, c, requests_per_level, max_tokens))
        record.levels.append(level)
    return record
