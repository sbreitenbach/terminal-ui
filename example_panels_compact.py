"""
example_panels_compact.py — Compact Horizontal Panel Dashboard

A space-efficient horizontal layout with:
- Single-row status bar at top
- Compact endpoint results in columns
- Inline progress and stats, minimal chrome
"""

import asyncio
import sys
from rich.console import Console, Group
from rich.layout import Layout
from rich.live import Live
from rich.panel import Panel
from rich.table import Table
from rich.text import Text
from rich.align import Align
from rich.columns import Columns

import scanner_sim as sim


def make_layout() -> Layout:
    layout = Layout()
    layout.split_column(
        Layout(name="status_bar", size=3),
        Layout(name="body"),
    )
    layout["body"].split_row(
        Layout(name="col1", ratio=1),
        Layout(name="col2", ratio=1),
        Layout(name="col3", ratio=1),
    )
    return layout


def status_bar_scanning(run_number: int, current: int, total: int, elapsed: float) -> Panel:
    """Compact status bar for scanning state."""
    grid = Table.grid(expand=True)
    grid.add_column(justify="left", ratio=1)
    grid.add_column(justify="center", ratio=2)
    grid.add_column(justify="right", ratio=1)

    # Inline progress
    pct = int(current / total * 20)
    bar_text = Text()
    bar_text.append("▐", style="bright_red")
    bar_text.append("█" * pct, style="bright_red")
    bar_text.append("░" * (20 - pct), style="bright_black")
    bar_text.append(f" {current/total*100:.0f}%", style="bold")

    grid.add_row(
        Text.assemble(("◉ ", "bright_red"), ("SCAN ", "bold bright_red"), (f"#{run_number}", "dim")),
        bar_text,
        Text(f"{sim.format_duration(elapsed)} elapsed  {current/total*100:.0f}% done", style="dim"),
    )
    return Panel(grid, border_style="red", style="on white")


def status_bar_idle(remaining: float, total_runs: int) -> Panel:
    """Compact status bar for idle state."""
    grid = Table.grid(expand=True)
    grid.add_column(justify="left", ratio=1)
    grid.add_column(justify="center", ratio=2)
    grid.add_column(justify="right", ratio=1)

    grid.add_row(
        Text.assemble(("● ", "green"), ("IDLE", "dim green")),
        Text(f"Next scan in {sim.format_duration(remaining)}", style="bold"),
        Text(f"{total_runs} runs completed", style="dim"),
    )
    return Panel(grid, border_style="dim green", style="on white")


def endpoint_card(result: sim.EndpointResult) -> Panel:
    """A tiny card for one endpoint result."""
    ms_style = "green" if result.response_time_ms < 200 else "yellow" if result.response_time_ms < 1000 else "red"
    border = "green" if result.status == sim.EndpointStatus.OK else "yellow" if result.status == sim.EndpointStatus.SLOW else "red"

    content = Text()
    content.append(f"{sim.status_emoji(result.status)} ", style="")
    content.append(f"{result.response_time_ms}ms", style=f"bold {ms_style}")
    content.append(f"\n{result.method}", style="dim cyan")
    content.append(f" {result.status_code or '---'}", style="dim")

    # Truncate endpoint to last 2 segments
    ep_short = "/".join(result.endpoint.split("/")[-2:])
    return Panel(content, title=f"[dim]{ep_short}[/dim]", border_style=border, width=22, height=5)


async def run_example(timing: sim.TimingConfig):
    console = Console()
    layout = make_layout()

    def scanning_cb(run_number, current, total, result, results, start_time, history):
        elapsed = sim.time.time() - start_time

        # Status bar
        layout["status_bar"].update(status_bar_scanning(run_number, current, total, elapsed))

        # Distribute results across 3 columns
        col_size = max(1, len(results) // 3 + 1)
        cols = [results[i:i + col_size] for i in range(0, len(results), col_size)]

        for idx, col_name in enumerate(["col1", "col2", "col3"]):
            if idx < len(cols):
                cards = Group(*[endpoint_card(r) for r in cols[idx][-4:]])
                layout[col_name].update(cards)
            else:
                layout[col_name].update(Panel("", border_style="bright_black"))
                
        return layout

    def idle_cb(remaining, summary, history, wait_start):
        layout["status_bar"].update(status_bar_idle(remaining, len(history)))

        # Col 1: Last scan summary
        sum_table = Table.grid(padding=(0, 1))
        sum_table.add_column()
        sum_table.add_column()
        rc = "green" if summary.passed else "red"
        sum_table.add_row("Result:", Text("PASS" if summary.passed else "FAIL", style=f"bold {rc}"))
        sum_table.add_row("OK:", Text(str(summary.total_ok), style="green"))
        sum_table.add_row("Errors:", Text(str(summary.total_errors), style="red"))
        sum_table.add_row("Timeouts:", Text(str(summary.total_timeouts), style="magenta"))
        sum_table.add_row("Avg:", Text(f"{summary.avg_response_ms:.0f}ms", style="blue"))
        layout["col1"].update(Panel(sum_table, title="[dim]Last Scan[/dim]", border_style="bright_blue"))

        # Col 2: History
        hist_table = Table(box=None, show_header=True, header_style="dim")
        hist_table.add_column("#", justify="center")
        hist_table.add_column("Status", justify="center")
        hist_table.add_column("Avg", justify="right")
        for h in history[-8:]:
            hist_table.add_row(
                str(h.run_number),
                Text("✓", style="green") if h.passed else Text("✗", style="red"),
                f"{h.avg_response_ms:.0f}ms",
            )
        layout["col2"].update(Panel(hist_table, title="[dim]History[/dim]", border_style="bright_blue"))

        # Col 3: Uptime stats
        total_scanned = sum(len(h.results) for h in history)
        total_ok = sum(h.total_ok for h in history)
        pass_rate = (total_ok / total_scanned * 100) if total_scanned else 0
        overall_avg = sum(h.avg_response_ms for h in history) / len(history) if history else 0

        stats_table = Table.grid(padding=(0, 1))
        stats_table.add_column()
        stats_table.add_column()
        stats_table.add_row("Total Scans:", Text(str(len(history)), style="bold"))
        stats_table.add_row("Endpoints:", Text(str(total_scanned), style="bold"))
        stats_table.add_row("Pass Rate:", Text(f"{pass_rate:.1f}%", style="green" if pass_rate > 95 else "yellow"))
        stats_table.add_row("Overall Avg:", Text(f"{overall_avg:.0f}ms", style="blue"))
        layout["col3"].update(Panel(stats_table, title="[dim]Overall[/dim]", border_style="bright_blue"))
        
        return layout

    await sim.run_app(
        timing,
        scanning_callback=scanning_cb,
        idle_callback=idle_cb,
        base_renderable=layout,
        console=console,
        scan_fps=10,
        idle_fps=4
    )


if __name__ == "__main__":
    try:
        timing = sim.parse_args()
        asyncio.run(run_example(timing))
    except KeyboardInterrupt:
        sys.exit(0)
