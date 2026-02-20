import asyncio
import sys
from rich.live import Live
from rich.panel import Panel
from rich.progress import Progress, BarColumn, TextColumn, SpinnerColumn
from rich.table import Table
from rich.console import Console, Group
from rich.text import Text

import scanner_sim as sim

SPARK_CHARS = "▁▂▃▄▅▆▇█"

def mini_sparkline(values, width=20):
    """Tiny inline sparkline of response times."""
    if not values:
        return Text("─" * width, style="dim")
    vals = values[-width:]
    mn, mx = min(vals), max(vals)
    rng = mx - mn if mx != mn else 1
    text = Text()
    for v in vals:
        idx = int((v - mn) / rng * (len(SPARK_CHARS) - 1))
        style = "green" if v < 200 else "yellow" if v < 1000 else "red"
        text.append(SPARK_CHARS[idx], style=style)
    remaining = width - len(vals)
    if remaining > 0:
        text.append("─" * remaining, style="dim")
    return text

def minimal_scanning(run_number, current, total, result, results, start_time, history):
    # Header info
    status_text = Text.assemble(
        ("● ", "red"), "SCANNING ", ("Run #", "dim"), (str(run_number), "bold"),
        f" | {current}/{total} endpoints"
    )
    
    # Progress bar
    progress = Progress(
        SpinnerColumn(),
        TextColumn("[progress.description]{task.description}"),
        BarColumn(),
        TextColumn("[progress.percentage]{task.percentage:>3.0f}%"),
    )
    progress.add_task("Progress", total=total, completed=current)
    
    # Mini sparkline of response times
    latencies = [r.response_time_ms for r in results]
    spark_row = Text.assemble(("  Latency: ", "dim"))
    spark_row.append_text(mini_sparkline(latencies, 25))
    
    # Stats with distribution
    ok_count = sum(1 for r in results if r.status == sim.EndpointStatus.OK)
    fail_count = sum(1 for r in results if r.status in [sim.EndpointStatus.ERROR, sim.EndpointStatus.TIMEOUT])
    slow_count = sum(1 for r in results if r.status == sim.EndpointStatus.SLOW)
    avg_ms = sum(r.response_time_ms for r in results) / len(results) if results else 0
    
    stats_table = Table.grid(padding=(0, 2))
    stats_table.add_row(
        f"OK: [green]{ok_count}[/green]",
        f"Slow: [yellow]{slow_count}[/yellow]",
        f"Fail: [red]{fail_count}[/red]",
        f"Avg: [blue]{avg_ms:.0f}ms[/blue]"
    )
    
    # Response time distribution
    fast = sum(1 for r in results if r.response_time_ms < 200)
    med = sum(1 for r in results if 200 <= r.response_time_ms < 1000)
    slow_ms = sum(1 for r in results if r.response_time_ms >= 1000)
    dist_text = Text.assemble(
        ("  ", ""), ("<200ms ", "dim"), (f"{fast}", "green"),
        ("  200-1s ", "dim"), (f"{med}", "yellow"),
        ("  >1s ", "dim"), (f"{slow_ms}", "red")
    )
    
    # Last 8 results
    results_table = Table(box=None, padding=(0, 1), show_header=False)
    for r in results[-8:]:
        ms_style = "green" if r.response_time_ms < 200 else "yellow" if r.response_time_ms < 1000 else "red"
        results_table.add_row(
            sim.status_emoji(r.status),
            Text(r.method, style="dim cyan"),
            f"[dim]{r.endpoint}[/dim]",
            Text(f"{r.response_time_ms}ms", style=f"bold {ms_style}")
        )
    
    return Panel(
        Group(status_text, progress, spark_row, stats_table, dist_text, Text(""), results_table),
        title="[bold blue]API Scanner[/bold blue]",
        border_style="blue"
    )

def minimal_idle(remaining, summary, history, wait_start):
    # Header info
    status_text = Text.assemble(
        ("● ", "green"), "IDLE ", ("Last scan: ", "dim"), (sim.format_time(summary.end_time), "bold"),
        f" | Next scan in {sim.format_duration(remaining)}"
    )
    
    # Sparkline of all latencies from last run
    latencies = [r.response_time_ms for r in summary.results]
    spark_row = Text.assemble(("  Latency: ", "dim"))
    spark_row.append_text(mini_sparkline(latencies, 25))
    
    # Summary of last run
    last_run_info = Table.grid(padding=(0, 2))
    last_run_info.add_row(
        f"Last Result: {'[green]PASSED[/green]' if summary.passed else '[red]FAILED[/red]'}",
        f"Points: {len(summary.results)}",
        f"Avg Resp: {summary.avg_response_ms:.0f}ms"
    )

    return Panel(
        Group(status_text, spark_row, last_run_info),
        title="[bold blue]API Scanner[/bold blue]",
        border_style="dim blue"
    )

async def run_example(timing: sim.TimingConfig):
    await sim.run_app(
        timing,
        scanning_callback=minimal_scanning,
        idle_callback=minimal_idle,
        scan_fps=10,
        idle_fps=4
    )

if __name__ == "__main__":
    try:
        timing = sim.parse_args()
        asyncio.run(run_example(timing))
    except KeyboardInterrupt:
        sys.exit(0)
