"""
CLI entry point: python -m app.ingest --source linkedin --file exports/export.zip
"""

import argparse
import asyncio
from pathlib import Path

import ingestion.adapters  # noqa: F401 — triggers @register decorators for all adapters
from ingestion.base import REGISTRY
from kb.pipeline import run_ingestion


async def main() -> None:
    parser = argparse.ArgumentParser(description="Ingest a social export into Cortex")
    parser.add_argument("--source", required=True, choices=sorted(REGISTRY), help="Platform")
    parser.add_argument("--file", required=True, type=Path, help="Export zip or directory")
    args = parser.parse_args()

    adapter = REGISTRY[args.source]()
    items = adapter.parse(args.file)

    def progress(snap: dict) -> None:
        # Live single-line update: batches done, running counts, elapsed.
        print(
            f"\r  batch {snap['batches']:>4} | "
            f"{snap['inserted']:>7} inserted | "
            f"{snap['dupes_skipped']:>7} dupes | "
            f"{snap['total_chunks']:>7} chunks | "
            f"{snap['elapsed']:>6}s",
            end="",
            flush=True,
        )

    print(f"Ingesting {args.source} from {args.file} ...")
    stats = await run_ingestion(items, on_progress=progress)
    print()  # newline after the live-updating progress line
    print(
        f"Done. chunks={stats['total_chunks']} "
        f"inserted={stats['inserted']} "
        f"dupes_skipped={stats['dupes_skipped']} "
        f"batches={stats['batches']}"
    )


if __name__ == "__main__":
    asyncio.run(main())
