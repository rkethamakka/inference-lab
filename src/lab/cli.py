"""`lab` command: manifest checks, server command rendering, benchmarks."""

from __future__ import annotations

import argparse
import sys

from lab import bench, manifest, serve


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="lab")
    parser.add_argument("--manifest", default=str(manifest.DEFAULT_PATH))
    sub = parser.add_subparsers(dest="cmd", required=True)

    check = sub.add_parser("check", help="validate the toolchain manifest")
    check.add_argument("--strict", action="store_true", help="fail on unpinned versions")

    srv = sub.add_parser("serve-cmd", help="print the vLLM command for a platform")
    srv.add_argument("--platform", choices=manifest.PLATFORMS, required=True)
    srv.add_argument("--port", type=int, default=8000)
    srv.add_argument("--cache-root", default=None)

    b = sub.add_parser("bench", help="benchmark an OpenAI-compatible endpoint")
    b.add_argument("--url", default="http://localhost:8000")
    b.add_argument("--platform", choices=manifest.PLATFORMS, required=True)
    b.add_argument("--concurrency", default="1,4,16")
    b.add_argument("--requests", type=int, default=16)
    b.add_argument("--max-tokens", type=int, default=128)

    args = parser.parse_args(argv)

    try:
        m = manifest.load(args.manifest, strict=getattr(args, "strict", False))
    except manifest.ManifestError as e:
        print(f"manifest error: {e}", file=sys.stderr)
        return 1

    if args.cmd == "check":
        print(f"manifest ok, hash {m.hash()}")
        for item in m.unpinned():
            print(f"  unpinned: {item}")
    elif args.cmd == "serve-cmd":
        print(serve.render(m, args.platform, args.port, args.cache_root))
    elif args.cmd == "bench":
        levels = tuple(int(x) for x in args.concurrency.split(","))
        record = bench.run(
            args.url, m.model["id"], args.platform, m.hash(), levels, args.requests, args.max_tokens
        )
        print(record.to_json())
    return 0


if __name__ == "__main__":
    sys.exit(main())
