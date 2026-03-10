from __future__ import annotations

import time
from dataclasses import dataclass

import requests


@dataclass
class FetchResult:
    ok: bool
    text: str
    latency_ms: int
    error_type: str
    message: str


def fetch_with_retry(url: str, timeout: int = 8, retries: int = 2) -> FetchResult:
    last_error_type = "unknown"
    last_message = ""
    for _ in range(retries + 1):
        started = time.perf_counter()
        try:
            resp = requests.get(
                url,
                timeout=timeout,
                headers={
                    "User-Agent": (
                        "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
                        "AppleWebKit/537.36 (KHTML, like Gecko) "
                        "Chrome/131.0.0.0 Safari/537.36"
                    )
                },
            )
            latency = int((time.perf_counter() - started) * 1000)
            if resp.status_code >= 400:
                last_error_type = "http"
                last_message = f"status={resp.status_code}"
                continue
            return FetchResult(ok=True, text=resp.text, latency_ms=latency, error_type="", message="ok")
        except requests.Timeout:
            last_error_type = "timeout"
            last_message = "request timeout"
        except requests.RequestException as exc:
            last_error_type = "network"
            last_message = str(exc)

    return FetchResult(ok=False, text="", latency_ms=0, error_type=last_error_type, message=last_message)
