"""
example_cylon.py — Cylon Raider Eye Scanner

Features a sweeping red light bar that moves left-to-right-to-left
during active scans (like the iconic Cylon from Battlestar Galactica),
and a slow, dim pulse when idle/waiting.
"""

import asyncio
import sys
import math
from rich.live import Live
from rich.panel import Panel
from rich.table import Table
from rich.console import Console, Group
from rich.text import Text
from rich.align import Align

import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', '..'))
import scanner_sim as sim


# ── Cylon Eye Animation ──────────────────────────────────────────────────────

def cylon_eye(width: int = 40, speed: float = 1.0, bright: bool = True) -> Text:
    """
    Generate a single frame of the Cylon eye sweep.
    The 'eye' is a bright core with fading trail on both sides.
    """
    t = sim.time.time() * speed
    # Ping-pong position across the width
    cycle = t % (2 * (width - 1))
    if cycle < width:
        pos = int(cycle)
    else:
        pos = int(2 * (width - 1) - cycle)

    text = Text()
    for i in range(width):
        dist = abs(i - pos)
        if dist == 0:
            char = "█"
            style = "bold bright_red" if bright else "red"
        elif dist == 1:
            char = "▓"
            style = "bright_red" if bright else "dark_red"
        elif dist == 2:
            char = "▒"
            style = "red" if bright else "dark_red"
        elif dist == 3:
            char = "░"
            style = "dark_red" if bright else "dim red"
        else:
            char = "─"
            style = "bright_black"
        text.append(char, style=style)
    return text


def cylon_idle_pulse(width: int = 40) -> Text:
    """
    Generate a slow breathing pulse for idle state.
    A dim red glow that expands and contracts from center.
    """
    t = sim.time.time()
    # Slow sine wave for breathing effect
    breath = (math.sin(t * 1.5) + 1) / 2  # 0.0 to 1.0
    pulse_width = int(breath * (width // 3)) + 1
    center = width // 2

    text = Text()
    for i in range(width):
        dist = abs(i - center)
        if dist < pulse_width:
            intensity = 1.0 - (dist / pulse_width)
            if intensity > 0.7:
                text.append("█", style="dark_red")
            elif intensity > 0.4:
                text.append("▓", style="dark_red")
            else:
                text.append("░", style="dim red")
        else:
            text.append("─", style="bright_black")
    return text


# ── UI Rendering ─────────────────────────────────────────────────────────────

async def run_example(timing: sim.TimingConfig):
    console = Console()

    def scanning_cb(run_number, current, total, result, results, start_time, history):
        # Cylon eye — fast sweep during active scan
        eye = cylon_eye(width=50, speed=3.0, bright=True)

        # Header
        header_text = Text()
        header_text.append("  ◉ SCANNING", style="bold bright_red")
        header_text.append(f"  Run #{run_number}", style="dim")
        header_text.append(f"  [{current}/{total}]", style="bold black")

        # Stats row
        ok = sum(1 for r in results if r.status == sim.EndpointStatus.OK)
        fail = sum(1 for r in results if r.status in (sim.EndpointStatus.ERROR, sim.EndpointStatus.TIMEOUT))
        slow = sum(1 for r in results if r.status == sim.EndpointStatus.SLOW)
        avg_ms = sum(r.response_time_ms for r in results) / len(results) if results else 0

        stats = Text()
        stats.append("  OK ", style="dim")
        stats.append(f"{ok}", style="bold green")
        stats.append("  ·  Fail ", style="dim")
        stats.append(f"{fail}", style="bold red" if fail > 0 else "dim")
        stats.append("  ·  Slow ", style="dim")
        stats.append(f"{slow}", style="bold yellow" if slow > 0 else "dim")
        stats.append("  ·  Avg ", style="dim")
        stats.append(f"{avg_ms:.0f}ms", style="bold blue")

        # Endpoint results (last 8)
        results_table = Table(box=None, show_header=True, header_style="dim", padding=(0, 1))
        results_table.add_column("", width=2)
        results_table.add_column("Method", width=5)
        results_table.add_column("Endpoint", min_width=24)
        results_table.add_column("Latency", justify="right", width=8)
        results_table.add_column("Code", justify="right", width=4)
        for r in results[-8:]:
            emoji = sim.status_emoji(r.status)
            ep_style = "dim" if r.status == sim.EndpointStatus.OK else "bold"
            ms_style = "cyan" if r.response_time_ms < 500 else "yellow" if r.response_time_ms < 2000 else "red"
            results_table.add_row(
                emoji,
                Text(r.method, style="dim cyan"),
                Text(r.endpoint, style=ep_style),
                Text(f"{r.response_time_ms}ms", style=ms_style),
                Text(f"{r.status_code}", style="dim") if r.status_code else Text("---", style="dim"),
            )

        return Panel(
            Group(
                header_text,
                Text(""),
                Align.center(eye),
                Text(""),
                stats,
                Text(""),
                results_table,
            ),
            title="[bold red]⟨ CYLON SCANNER ⟩[/bold red]",
            border_style="red",
            padding=(1, 2),
        )

    def idle_cb(remaining, summary, history, wait_start):
        # Idle pulse — slow breathing
        eye = cylon_idle_pulse(width=50)

        # Header
        header_text = Text()
        header_text.append("  ● IDLE", style="dim green")
        header_text.append(f"  Next scan in ", style="dim")
        header_text.append(sim.format_duration(remaining), style="bold black")

        # Last scan summary
        result_color = "green" if summary.passed else "red"
        summary_text = Text()
        summary_text.append(f"  Last: ", style="dim")
        summary_text.append("PASS" if summary.passed else "FAIL", style=f"bold {result_color}")
        summary_text.append(f"  ·  {len(summary.results)} endpoints", style="dim")
        summary_text.append(f"  ·  {summary.avg_response_ms:.0f}ms avg", style="dim")
        summary_text.append(f"  ·  {sim.format_time(summary.end_time)}", style="dim")

        # History (last 5 runs)
        if history:
            hist_table = Table(box=None, show_header=True, padding=(0, 1))
            hist_table.add_column("Run", justify="center", style="dim")
            hist_table.add_column("Result", justify="center")
            hist_table.add_column("Avg", justify="right", style="cyan")
            hist_table.add_column("Time", justify="right", style="dim")
            for h in history[-5:]:
                hist_table.add_row(
                    f"#{h.run_number}",
                    Text("PASS", style="green") if h.passed else Text("FAIL", style="red"),
                    f"{h.avg_response_ms:.0f}ms",
                    sim.format_time(h.end_time),
                )
        else:
            hist_table = Text("  No history yet", style="dim")

        return Panel(
            Group(
                header_text,
                Text(""),
                Align.center(eye),
                Text(""),
                summary_text,
                Text(""),
                hist_table,
            ),
            title="[dim red]⟨ CYLON SCANNER ⟩[/dim red]",
            border_style="bright_black",
            padding=(1, 2),
        )

    await sim.run_app(
        timing,
        scanning_callback=scanning_cb,
        idle_callback=idle_cb,
        console=console,
        scan_fps=15,
        idle_fps=10
    )


if __name__ == "__main__":
    try:
        timing = sim.parse_args()
        asyncio.run(run_example(timing))
    except KeyboardInterrupt:
        sys.exit(0)
