"""
scanner_sim.py — Shared simulation module for terminal UI prototypes.

Provides fake API scan results with realistic timing and macOS notifications.
All 3 example UIs import from this module.
"""

import asyncio
import random
import subprocess
import time
from dataclasses import dataclass, field
from enum import Enum
from typing import AsyncGenerator


# ── Fake API endpoints to "scan" ──────────────────────────────────────────────

ENDPOINTS = [
    "/api/v1/users",
    "/api/v1/users/profile",
    "/api/v1/auth/token",
    "/api/v1/auth/refresh",
    "/api/v1/orders",
    "/api/v1/orders/history",
    "/api/v1/products",
    "/api/v1/products/search",
    "/api/v1/inventory",
    "/api/v1/payments",
    "/api/v1/notifications",
    "/api/v1/health",
]

# HTTP methods mapped to endpoints by route semantics
ENDPOINT_METHODS = {
    "/api/v1/users": "GET",
    "/api/v1/users/profile": "GET",
    "/api/v1/auth/token": "POST",
    "/api/v1/auth/refresh": "POST",
    "/api/v1/orders": "GET",
    "/api/v1/orders/history": "GET",
    "/api/v1/products": "GET",
    "/api/v1/products/search": "POST",
    "/api/v1/inventory": "PUT",
    "/api/v1/payments": "POST",
    "/api/v1/notifications": "GET",
    "/api/v1/health": "GET",
}

def get_method(endpoint: str) -> str:
    """Return the HTTP method for a given endpoint."""
    return ENDPOINT_METHODS.get(endpoint, "GET")


class EndpointStatus(Enum):
    OK = "ok"
    SLOW = "slow"
    TIMEOUT = "timeout"
    ERROR = "error"


@dataclass
class EndpointResult:
    """Result of scanning a single endpoint."""
    endpoint: str
    status: EndpointStatus
    response_time_ms: int
    status_code: int
    method: str = "GET"
    timestamp: float = field(default_factory=time.time)


@dataclass
class ScanSummary:
    """Summary of a complete scan run."""
    run_number: int
    results: list[EndpointResult]
    start_time: float
    end_time: float
    total_ok: int = 0
    total_slow: int = 0
    total_errors: int = 0
    total_timeouts: int = 0
    avg_response_ms: float = 0.0

    def __post_init__(self):
        self.total_ok = sum(1 for r in self.results if r.status == EndpointStatus.OK)
        self.total_slow = sum(1 for r in self.results if r.status == EndpointStatus.SLOW)
        self.total_errors = sum(1 for r in self.results if r.status == EndpointStatus.ERROR)
        self.total_timeouts = sum(1 for r in self.results if r.status == EndpointStatus.TIMEOUT)
        if self.results:
            self.avg_response_ms = sum(r.response_time_ms for r in self.results) / len(self.results)

    @property
    def passed(self) -> bool:
        return self.total_errors == 0 and self.total_timeouts == 0

    @property
    def duration(self) -> float:
        return self.end_time - self.start_time


# ── Timing configuration ─────────────────────────────────────────────────────

@dataclass
class TimingConfig:
    """Controls scan and wait durations."""
    scan_duration_seconds: float  # Total time a scan takes
    wait_duration_seconds: float  # Time between scans

    @classmethod
    def demo(cls) -> "TimingConfig":
        """Accelerated timing for demo/evaluation (15s scan, 30s wait)."""
        return cls(scan_duration_seconds=15.0, wait_duration_seconds=30.0)

    @classmethod
    def real(cls) -> "TimingConfig":
        """Production timing (60s scan, 300s wait)."""
        return cls(scan_duration_seconds=60.0, wait_duration_seconds=300.0)


# ── Scan simulation ──────────────────────────────────────────────────────────

def _generate_result(endpoint: str) -> EndpointResult:
    """Generate a realistic fake scan result for an endpoint."""
    method = get_method(endpoint)
    roll = random.random()

    if roll < 0.75:
        # Normal response
        response_time = random.randint(30, 250)
        return EndpointResult(
            endpoint=endpoint,
            status=EndpointStatus.OK,
            response_time_ms=response_time,
            status_code=200,
            method=method,
        )
    elif roll < 0.88:
        # Slow response
        response_time = random.randint(800, 2500)
        return EndpointResult(
            endpoint=endpoint,
            status=EndpointStatus.SLOW,
            response_time_ms=response_time,
            status_code=200,
            method=method,
        )
    elif roll < 0.96:
        # Error
        status_code = random.choice([500, 502, 503, 429])
        response_time = random.randint(50, 500)
        return EndpointResult(
            endpoint=endpoint,
            status=EndpointStatus.ERROR,
            response_time_ms=response_time,
            status_code=status_code,
            method=method,
        )
    else:
        # Timeout
        return EndpointResult(
            endpoint=endpoint,
            status=EndpointStatus.TIMEOUT,
            response_time_ms=5000,
            status_code=0,
            method=method,
        )


async def simulate_scan(
    timing: TimingConfig,
    run_number: int = 1,
) -> AsyncGenerator[tuple[int, int, EndpointResult], None]:
    """
    Async generator that yields scan results one at a time.

    Yields: (current_index, total_count, EndpointResult)
    Each yield is spaced out to fill the total scan_duration.
    """
    endpoints = ENDPOINTS.copy()
    random.shuffle(endpoints)
    total = len(endpoints)
    delay_per_endpoint = timing.scan_duration_seconds / total

    for i, endpoint in enumerate(endpoints):
        # Simulate network delay
        jitter = random.uniform(0.5, 1.5)
        await asyncio.sleep(delay_per_endpoint * jitter)

        result = _generate_result(endpoint)
        yield (i + 1, total, result)


# ── macOS notifications ──────────────────────────────────────────────────────

def send_notification(title: str, message: str, sound: str = "Ping") -> None:
    """
    Send a native macOS notification using osascript.
    Falls back silently if not on macOS or if notification fails.
    """
    try:
        script = (
            f'display notification "{message}" '
            f'with title "{title}" '
            f'sound name "{sound}"'
        )
        subprocess.run(
            ["osascript", "-e", script],
            capture_output=True,
            timeout=5,
        )
    except (FileNotFoundError, subprocess.TimeoutExpired, OSError):
        pass  # Silently fail on non-macOS or errors


def notify_scan_complete(summary: ScanSummary) -> None:
    """Send a notification summarizing the scan results."""
    if summary.passed:
        title = "✅ API Scan Passed"
        message = (
            f"Run #{summary.run_number}: All {len(summary.results)} endpoints OK. "
            f"Avg {summary.avg_response_ms:.0f}ms"
        )
    else:
        title = "⚠️ API Scan Issues"
        issues = []
        if summary.total_errors > 0:
            issues.append(f"{summary.total_errors} errors")
        if summary.total_timeouts > 0:
            issues.append(f"{summary.total_timeouts} timeouts")
        message = f"Run #{summary.run_number}: {', '.join(issues)} detected"

    send_notification(title, message)


# ── Utilities ─────────────────────────────────────────────────────────────────

def format_duration(seconds: float) -> str:
    """Format seconds as M:SS."""
    minutes = int(seconds) // 60
    secs = int(seconds) % 60
    return f"{minutes}:{secs:02d}"


def format_time(timestamp: float) -> str:
    """Format a timestamp as HH:MM:SS."""
    return time.strftime("%H:%M:%S", time.localtime(timestamp))


def status_emoji(status: EndpointStatus) -> str:
    """Return an emoji for the endpoint status."""
    return {
        EndpointStatus.OK: "✅",
        EndpointStatus.SLOW: "🟡",
        EndpointStatus.TIMEOUT: "⏱️ ",
        EndpointStatus.ERROR: "❌",
    }[status]


def parse_args():
    """Parse command-line arguments shared by all examples."""
    import argparse
    parser = argparse.ArgumentParser(description="Terminal UI API Scanner Prototype")
    parser.add_argument(
        "--real-timing",
        action="store_true",
        help="Use real timing (1 min scan, 5 min wait) instead of demo timing",
    )
    args = parser.parse_args()
    return TimingConfig.real() if args.real_timing else TimingConfig.demo()
