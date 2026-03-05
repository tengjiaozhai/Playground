#!/usr/bin/env python3
"""Normalize multi-source payloads to the project unified ingestion schema."""

from __future__ import annotations

import argparse


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Normalize source payload to unified schema")
    parser.add_argument("--input", required=True, help="Path to raw input JSON/JSONL")
    parser.add_argument("--output", required=True, help="Path to normalized output JSONL")
    parser.add_argument("--source", required=True, help="Source key")
    return parser.parse_args()


def main() -> None:
    _ = parse_args()
    raise NotImplementedError("Implementation is intentionally deferred to roadmap V2.")


if __name__ == "__main__":
    main()
