#!/usr/bin/env python3
"""Score normalized sentiment signals into decision-ready features."""

from __future__ import annotations

import argparse


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Score normalized sentiment signals")
    parser.add_argument("--input", required=True, help="Path to normalized signals JSONL")
    parser.add_argument("--output", required=True, help="Path to scored feature JSONL")
    parser.add_argument("--risk-mode", default="balanced", choices=["strong", "balanced", "aggressive"])
    return parser.parse_args()


def main() -> None:
    _ = parse_args()
    raise NotImplementedError("Implementation is intentionally deferred to roadmap V3.")


if __name__ == "__main__":
    main()
