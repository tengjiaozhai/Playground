#!/usr/bin/env python3
"""Generate markdown/html daily reports from recommendation snapshots."""

from __future__ import annotations

import argparse


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Generate daily report from recommendations")
    parser.add_argument("--input", required=True, help="Path to recommendation snapshot")
    parser.add_argument("--date", required=True, help="Report date (YYYY-MM-DD)")
    parser.add_argument("--md-output", required=True, help="Markdown output path")
    parser.add_argument("--html-output", required=True, help="HTML output path")
    return parser.parse_args()


def main() -> None:
    _ = parse_args()
    raise NotImplementedError("Implementation is intentionally deferred to roadmap V4.")


if __name__ == "__main__":
    main()
