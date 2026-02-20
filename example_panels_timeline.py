"""
example_panels_timeline.py — Timeline Panel Dashboard

A chronological, timeline-focused dashboard with:
- Vertical timeline of scan events
- Status dots and connectors
- Time-anchored history with relative timestamps
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

import scanner_sim as sim


def make_layout() -> Layout:
    layout = Layout()
    layout.split_column(
        Layout(name="header", size=5),
        Layout(name="body"),
    )
    layout["body"].split_row(
        Layout(name="timeline", ratio=2),
        Layout(name="sidebar", ratio=1),
    )
    layout["sidebar"].split_column(
        Layout(name="stats", ratio=1),
        Layout(name="details", ratio=1),
    )
    return layout


# ── Timeline Rendering ────────────────────────────────────────────────────────

def render_timeline_scanning(results: list[sim.EndpointResult], current: int, total: int, start_time: float) -> Panel:
    """Render a vertical timeline of scan events in progress."""
    table = Table(box=None, show_header=False, padding=(0, 1), expand=True)
    table.add_column("T", width=10, justify="right")  # Time
    table.add_column("│", width=3, justify="center")  # Connector
    table.add_column("Event")  # Description

    for i, r in enumerate(results[-15:]):
        time_str = sim.format_time(r.timestamp)
        elapsed = r.timestamp - start_time
        is_last = (i == len(results[-15:]) - 1)

        # Connector with vertical line continuity
        if is_last:
            connector = Text("◉", style="bold bright_red")
        elif r.status == sim.EndpointStatus.OK:
            connector = Text("●", style="green")
        elif r.status == sim.EndpointStatus.SLOW:
            connector = Text("●", style="yellow")
        else:
            connector = Text("●", style="red")

        # Event description with method, status code, and elapsed
        ms_style = "green" if r.response_time_ms < 200 else "yellow" if r.response_time_ms < 1000 else "red"
        event = Text()
        event.append(f"{r.method} ", style="dim cyan")
        event.append(f"{r.endpoint} ", style="dim" if not is_last else "bold")
        event.append(f"→ {r.response_time_ms}ms ", style=ms_style)
        event.append(f"[{r.status_code or '---'}] ", style="dim")
        if r.status != sim.EndpointStatus.OK:
            event.append(f"[{r.status.value.upper()}] ", style="bold red")
        event.append(f"+{elapsed:.1f}s", style="dim blue")

        table.add_row(
            Text(time_str, style="dim blue"),
            connector,
            event,
        )

        # Add connector lines between entries (except after last)
        if not is_last:
            table.add_row(
                Text("", style="dim"),
                Text("│", style="dim"),
                Text("", style="dim"),
            )

    # Show remaining
    remaining = total - current
    if remaining > 0:
        table.add_row(
            Text("", style="dim"),
            Text("┆", style="dim"),
            Text(f"{remaining} more endpoint{'s' if remaining > 1 else ''} queued...", style="dim italic"),
        )

    return Panel(table, title="[bold blue]Timeline[/bold blue]", border_style="blue")


def render_timeline_history(history: list[sim.ScanSummary]) -> Panel:
    """Render a vertical timeline of past scan runs."""
    table = Table(box=None, show_header=False, padding=(0, 1), expand=True)
    table.add_column("T", width=10, justify="right")
    table.add_column("│", width=3, justify="center")
    table.add_column("Event")

    if not history:
        table.add_row(Text("--:--:--", style="dim"), Text("○", style="dim"), Text("No runs yet", style="dim italic"))
    else:
        for h in history[-12:]:
            time_str = sim.format_time(h.end_time)
            connector = Text("●", style="green") if h.passed else Text("●", style="red")

            event = Text()
            event.append(f"Run #{h.run_number} ", style="bold")
            event.append("PASS " if h.passed else "FAIL ", style="bold green" if h.passed else "bold red")
            event.append(f"· {len(h.results)}ep · {h.avg_response_ms:.0f}ms avg", style="dim")
            if h.total_errors > 0:
                event.append(f" · {h.total_errors}err", style="red")
            if h.total_timeouts > 0:
                event.append(f" · {h.total_timeouts}t/o", style="magenta")

            table.add_row(
                Text(time_str, style="dim blue"),
                connector,
                event,
            )

    return Panel(table, title="[bold blue]Timeline[/bold blue]", border_style="dim blue")


# ── Main Loop ─────────────────────────────────────────────────────────────────

async def run_example(timing: sim.TimingConfig):
    console = Console()
    layout = make_layout()
    
    def scanning_cb(run_number, current, total, result, results, start_time, history):
        elapsed = sim.time.time() - start_time

        # Header — scan active
        pct = current / total * 100
        bar_width = 30
        filled = int(current / total * bar_width)
        bar = Text()
        bar.append("█" * filled, style="bright_blue")
        bar.append("░" * (bar_width - filled), style="white")

        header_content = Group(
            Text.assemble(
                ("  ◉ SCANNING", "bold bright_blue"),
                (f"  Run #{run_number}", "dim"),
                (f"  ·  {current}/{total}", "bold"),
                (f"  ·  {sim.format_duration(elapsed)} elapsed", "dim"),
            ),
            Align.center(Text.assemble(("  ", ""), bar, (f"  {pct:.0f}%", "bold"))),
        )
        layout["header"].update(Panel(header_content, border_style="blue", style="on white"))

        # Timeline
        layout["timeline"].update(render_timeline_scanning(results, current, total, start_time))

        # Stats sidebar
        ok = sum(1 for r in results if r.status == sim.EndpointStatus.OK)
        fail = sum(1 for r in results if r.status in (sim.EndpointStatus.ERROR, sim.EndpointStatus.TIMEOUT))
        slow = sum(1 for r in results if r.status == sim.EndpointStatus.SLOW)
        avg = sum(r.response_time_ms for r in results) / len(results) if results else 0

        stats_table = Table.grid(padding=(0, 1))
        stats_table.add_column(width=10)
        stats_table.add_column()
        stats_table.add_row(Text("OK", style="dim"), Text(str(ok), style="bold green"))
        stats_table.add_row(Text("Slow", style="dim"), Text(str(slow), style="bold yellow"))
        stats_table.add_row(Text("Errors", style="dim"), Text(str(fail), style="bold red"))
        stats_table.add_row(Text("Avg ms", style="dim"), Text(f"{avg:.0f}", style="bold blue"))
        layout["stats"].update(Panel(stats_table, title="[dim]Live Stats[/dim]", border_style="bright_blue"))

        # Details — latest endpoint
        detail_table = Table.grid(padding=(0, 1))
        detail_table.add_column(width=10)
        detail_table.add_column()
        detail_table.add_row(Text("Endpoint", style="dim"), Text(result.endpoint, style="bold"))
        detail_table.add_row(Text("Status", style="dim"), Text(result.status.value.upper(), style="bold green" if result.status == sim.EndpointStatus.OK else "bold red"))
        detail_table.add_row(Text("Latency", style="dim"), Text(f"{result.response_time_ms}ms", style="blue"))
        detail_table.add_row(Text("Code", style="dim"), Text(str(result.status_code) if result.status_code else "N/A", style="dim"))
        layout["details"].update(Panel(detail_table, title="[dim]Latest[/dim]", border_style="bright_blue"))
        
        return layout

    def idle_cb(remaining, summary, history, wait_start):
        # Header — idle
        header_content = Group(
            Text.assemble(
                ("  ● IDLE", "dim green"),
                (f"  ·  Next scan in ", "dim"),
                (sim.format_duration(remaining), "bold black"),
            ),
            Text(f"  Completed {len(history)} scan{'s' if len(history) != 1 else ''}", style="dim"),
        )
        layout["header"].update(Panel(header_content, border_style="dim green", style="on white"))

        # Timeline — history
        layout["timeline"].update(render_timeline_history(history))

        # Stats — overall
        total_ok = sum(h.total_ok for h in history)
        total_scanned = sum(len(h.results) for h in history)
        pass_rate = (total_ok / total_scanned * 100) if total_scanned else 0
        overall_avg = sum(h.avg_response_ms for h in history) / len(history) if history else 0

        stats_table = Table.grid(padding=(0, 1))
        stats_table.add_column(width=10)
        stats_table.add_column()
        stats_table.add_row(Text("Runs", style="dim"), Text(str(len(history)), style="bold"))
        stats_table.add_row(Text("Endpoints", style="dim"), Text(str(total_scanned), style="bold"))
        stats_table.add_row(Text("Pass Rate", style="dim"), Text(f"{pass_rate:.1f}%", style="green" if pass_rate > 95 else "yellow"))
        stats_table.add_row(Text("Avg ms", style="dim"), Text(f"{overall_avg:.0f}", style="cyan"))
        layout["stats"].update(Panel(stats_table, title="[dim]Overall[/dim]", border_style="grey30"))

        # Details — last run
        rc = "green" if summary.passed else "red"
        detail_table = Table.grid(padding=(0, 1))
        detail_table.add_column(width=10)
        detail_table.add_column()
        detail_table.add_row(Text("Run", style="dim"), Text(f"#{summary.run_number}", style="bold"))
        detail_table.add_row(Text("Result", style="dim"), Text("PASS" if summary.passed else "FAIL", style=f"bold {rc}"))
        detail_table.add_row(Text("Duration", style="dim"), Text(f"{summary.duration:.1f}s", style="dim"))
        detail_table.add_row(Text("Avg ms", style="dim"), Text(f"{summary.avg_response_ms:.0f}", style="cyan"))
        layout["details"].update(Panel(detail_table, title="[dim]Last Run[/dim]", border_style="grey30"))

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
