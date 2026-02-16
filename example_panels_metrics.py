"""
example_panels_metrics.py — Metrics Panel Dashboard (Solarized Light)

A data-heavy metrics dashboard optimized for light themes:
- Color-coded response time gauges
- Sparkline-style mini charts for latency trends
- Dense stats layout optimized for monitoring
"""

import asyncio
import sys
import math
from rich.console import Console, Group
from rich.layout import Layout
from rich.live import Live
from rich.panel import Panel
from rich.table import Table
from rich.text import Text
from rich.align import Align
from rich.rule import Rule

import scanner_sim as sim


# ── Sparkline / Mini Chart ────────────────────────────────────────────────────

SPARK_CHARS = "▁▂▃▄▅▆▇█"

def sparkline(values: list[float], width: int = 20) -> Text:
    """Render a sparkline from a list of values."""
    if not values:
        return Text("─" * width, style="dim")
    # Take the last `width` values
    vals = values[-width:]
    mn, mx = min(vals), max(vals)
    rng = mx - mn if mx != mn else 1
    text = Text()
    for v in vals:
        idx = int((v - mn) / rng * (len(SPARK_CHARS) - 1))
        # Color based on value (lower is better for latency)
        if v < 200:
            style = "green"
        elif v < 500:
            style = "yellow"
        elif v < 1500:
            style = "dark_orange"
        else:
            style = "red"
        text.append(SPARK_CHARS[idx], style=style)
    # Pad remaining
    remaining = width - len(vals)
    if remaining > 0:
        text.append("─" * remaining, style="dim")
    return text


def gauge_bar(value: float, max_val: float, width: int = 15) -> Text:
    """Render a horizontal gauge bar."""
    pct = min(value / max_val, 1.0)
    filled = int(pct * width)
    text = Text()
    if pct < 0.5:
        style = "green"
    elif pct < 0.75:
        style = "yellow"
    else:
        style = "red"
    text.append("█" * filled, style=style)
    text.append("░" * (width - filled), style="white")
    return text


# ── Layout Builder ────────────────────────────────────────────────────────────

def make_layout() -> Layout:
    layout = Layout()
    layout.split_column(
        Layout(name="header", size=3),
        Layout(name="body"),
        Layout(name="footer", size=4),
    )
    layout["body"].split_row(
        Layout(name="metrics", ratio=1),
        Layout(name="feed", ratio=2),
    )
    layout["metrics"].split_column(
        Layout(name="gauges", ratio=1),
        Layout(name="sparklines", ratio=1),
    )
    return layout


async def run_example(timing: sim.TimingConfig):
    console = Console()
    layout = make_layout()
    history: list[sim.ScanSummary] = []
    all_latencies: list[float] = []
    run_number = 1

    while True:
        # ── SCANNING STATE ────────────────────────────────────────────────
        results: list[sim.EndpointResult] = []
        start_time = sim.time.time()

        with Live(layout, console=console, refresh_per_second=10):
            async for current, total, result in sim.simulate_scan(timing, run_number):
                results.append(result)
                all_latencies.append(result.response_time_ms)

                # Header
                elapsed = sim.time.time() - start_time
                header_grid = Table.grid(expand=True)
                header_grid.add_column(justify="left")
                header_grid.add_column(justify="center")
                header_grid.add_column(justify="right")
                header_grid.add_row(
                    Text.assemble(("◉ ", "bright_red"), ("SCANNING", "bold bright_red")),
                    Text(f"Run #{run_number}  ·  {current}/{total} endpoints", style="black"),
                    Text(f"Elapsed: {sim.format_duration(elapsed)}", style="dim"),
                )
                layout["header"].update(Panel(header_grid, style="on white", border_style="bright_red"))

                # Gauges panel
                ok = sum(1 for r in results if r.status == sim.EndpointStatus.OK)
                fail = sum(1 for r in results if r.status in (sim.EndpointStatus.ERROR, sim.EndpointStatus.TIMEOUT))
                avg = sum(r.response_time_ms for r in results) / len(results) if results else 0
                max_ms = max((r.response_time_ms for r in results), default=0)

                gauge_table = Table.grid(padding=(0, 1))
                gauge_table.add_column(width=9)
                gauge_table.add_column()
                gauge_table.add_row(Text("Health", style="dim"), gauge_bar(ok, total, 12))
                gauge_table.add_row(Text(f"  {ok}/{total}", style="green"), Text(""))
                gauge_table.add_row(Text("Avg ms", style="dim"), gauge_bar(avg, 2000, 12))
                gauge_table.add_row(Text(f"  {avg:.0f}", style="blue"), Text(""))
                gauge_table.add_row(Text("Max ms", style="dim"), gauge_bar(max_ms, 5000, 12))
                gauge_table.add_row(Text(f"  {max_ms}", style="magenta"), Text(""))
                layout["gauges"].update(Panel(gauge_table, title="[dim]Gauges[/dim]", border_style="bright_blue"))

                # Sparklines panel
                spark_table = Table.grid(padding=(0, 1))
                spark_table.add_column(width=9)
                spark_table.add_column()
                spark_table.add_row(Text("Latency", style="dim"), sparkline([r.response_time_ms for r in results], 18))
                # Per-run averages
                run_avgs = [h.avg_response_ms for h in history[-18:]]
                spark_table.add_row(Text("Run Avg", style="dim"), sparkline(run_avgs, 18))
                layout["sparklines"].update(Panel(spark_table, title="[dim]Trends[/dim]", border_style="bright_blue"))

                # Feed panel — live results
                feed_table = Table(box=None, expand=True, show_header=True, header_style="dim")
                feed_table.add_column("", width=2)
                feed_table.add_column("Endpoint")
                feed_table.add_column("Latency", justify="right")
                feed_table.add_column("Code", justify="right")
                for r in results[-12:]:
                    ms_style = "green" if r.response_time_ms < 200 else "yellow" if r.response_time_ms < 1000 else "red"
                    feed_table.add_row(
                        sim.status_emoji(r.status),
                        Text(r.endpoint, style="dim"),
                        Text(f"{r.response_time_ms}ms", style=ms_style),
                        Text(str(r.status_code) if r.status_code else "---", style="dim"),
                    )
                layout["feed"].update(Panel(feed_table, title="[dim]Live Feed[/dim]", border_style="bright_blue"))

                # Footer — progress
                pct = int(current / total * 30)
                bar = Text()
                bar.append("█" * pct, style="bright_red")
                bar.append("░" * (30 - pct), style="white")
                bar.append(f"  {current/total*100:.0f}%", style="bold")
                layout["footer"].update(Panel(
                    Align.center(bar),
                    border_style="bright_blue",
                ))

        # Scan complete
        summary = sim.ScanSummary(run_number, results, start_time, sim.time.time())
        history.append(summary)
        sim.notify_scan_complete(summary)
        run_number += 1

        # ── WAITING STATE ─────────────────────────────────────────────────
        wait_start = sim.time.time()

        with Live(layout, console=console, refresh_per_second=4):
            while True:
                elapsed = sim.time.time() - wait_start
                if elapsed >= timing.wait_duration_seconds:
                    break
                remaining = timing.wait_duration_seconds - elapsed

                # Header — idle
                header_grid = Table.grid(expand=True)
                header_grid.add_column(justify="left")
                header_grid.add_column(justify="center")
                header_grid.add_column(justify="right")
                header_grid.add_row(
                    Text.assemble(("● ", "green"), ("IDLE", "dim green")),
                    Text(f"Scans completed: {len(history)}", style="dim"),
                    Text(f"Next in: {sim.format_duration(remaining)}", style="bold black"),
                )
                layout["header"].update(Panel(header_grid, style="on white", border_style="dim green"))

                # Gauges — overall stats
                total_ok = sum(h.total_ok for h in history)
                total_fail = sum(h.total_errors + h.total_timeouts for h in history)
                total_scanned = sum(len(h.results) for h in history)
                overall_avg = sum(h.avg_response_ms for h in history) / len(history)

                gauge_table = Table.grid(padding=(0, 1))
                gauge_table.add_column(width=9)
                gauge_table.add_column()
                gauge_table.add_row(Text("Pass %", style="dim"), gauge_bar(total_ok, total_scanned, 12))
                gauge_table.add_row(Text(f"  {total_ok}/{total_scanned}", style="green"), Text(""))
                gauge_table.add_row(Text("Avg ms", style="dim"), gauge_bar(overall_avg, 2000, 12))
                gauge_table.add_row(Text(f"  {overall_avg:.0f}", style="cyan"), Text(""))
                layout["gauges"].update(Panel(gauge_table, title="[dim]Overall[/dim]", border_style="grey30"))

                # Sparklines — trends
                spark_table = Table.grid(padding=(0, 1))
                spark_table.add_column(width=9)
                spark_table.add_column()
                spark_table.add_row(Text("Latency", style="dim"), sparkline(all_latencies, 18))
                run_avgs = [h.avg_response_ms for h in history[-18:]]
                spark_table.add_row(Text("Run Avg", style="dim"), sparkline(run_avgs, 18))
                layout["sparklines"].update(Panel(spark_table, title="[dim]Trends[/dim]", border_style="grey30"))

                # Feed — history
                hist_table = Table(box=None, expand=True, show_header=True, header_style="dim")
                hist_table.add_column("Run", justify="center")
                hist_table.add_column("Result", justify="center")
                hist_table.add_column("OK", justify="right")
                hist_table.add_column("Fail", justify="right")
                hist_table.add_column("Avg", justify="right")
                hist_table.add_column("Time", justify="right")
                for h in history[-10:]:
                    hist_table.add_row(
                        f"#{h.run_number}",
                        Text("PASS", style="green") if h.passed else Text("FAIL", style="bold red"),
                        Text(str(h.total_ok), style="green"),
                        Text(str(h.total_errors + h.total_timeouts), style="red" if (h.total_errors + h.total_timeouts) > 0 else "dim"),
                        f"{h.avg_response_ms:.0f}ms",
                        sim.format_time(h.end_time),
                    )
                layout["feed"].update(Panel(hist_table, title="[dim]History[/dim]", border_style="grey30"))

                # Footer — countdown
                pct = int(elapsed / timing.wait_duration_seconds * 30)
                bar = Text()
                bar.append("█" * pct, style="dim green")
                bar.append("░" * (30 - pct), style="bright_black")
                bar.append(f"  {sim.format_duration(remaining)} remaining", style="dim")
                layout["footer"].update(Panel(Align.center(bar), border_style="grey30"))

                await asyncio.sleep(0.25)


if __name__ == "__main__":
    try:
        timing = sim.parse_args()
        asyncio.run(run_example(timing))
    except KeyboardInterrupt:
        sys.exit(0)
