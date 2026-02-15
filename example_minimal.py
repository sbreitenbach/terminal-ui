import asyncio
import sys
from rich.live import Live
from rich.panel import Panel
from rich.progress import Progress, BarColumn, TextColumn, SpinnerColumn
from rich.table import Table
from rich.console import Console, Group
from rich.text import Text

import scanner_sim as sim

async def run_example(timing: sim.TimingConfig):
    console = Console()
    history = []
    run_number = 1
    
    while True:
        # --- Scanning State ---
        results = []
        start_time = sim.time.time()
        
        with Live(refresh_per_second=10) as live:
            async for current, total, result in sim.simulate_scan(timing, run_number):
                results.append(result)
                
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
                
                # Mini stats
                stats_table = Table.grid(padding=(0, 2))
                stats_table.add_row(
                    f"OK: [green]{sum(1 for r in results if r.status == sim.EndpointStatus.OK)}[/green]",
                    f"Fail: [red]{sum(1 for r in results if r.status in [sim.EndpointStatus.ERROR, sim.EndpointStatus.TIMEOUT])}[/red]",
                    f"Avg: [cyan]{(sum(r.response_time_ms for r in results)/len(results)):.0f}ms[/cyan]" if results else "Avg: --"
                )
                
                # Last 5 results
                results_table = Table(box=None, padding=(0, 1), show_header=False)
                for r in results[-5:]:
                    results_table.add_row(
                        sim.status_emoji(r.status),
                        f"[dim]{r.endpoint}[/dim]",
                        f"[bold]{r.response_time_ms}ms[/bold]"
                    )
                
                live.update(Panel(
                    Group(status_text, progress, stats_table, results_table),
                    title="[bold blue]API Scanner[/bold blue]",
                    border_style="blue"
                ))

        # Scan complete
        summary = sim.ScanSummary(run_number, results, start_time, sim.time.time())
        history.append(summary)
        sim.notify_scan_complete(summary)
        run_number += 1
        
        # --- Waiting State ---
        wait_start = sim.time.time()
        while sim.time.time() - wait_start < timing.wait_duration_seconds:
            remaining = timing.wait_duration_seconds - (sim.time.time() - wait_start)
            
            # Header info
            status_text = Text.assemble(
                ("● ", "green"), "IDLE ", ("Last scan: ", "dim"), (sim.format_time(summary.end_time), "bold"),
                f" | Next scan in {sim.format_duration(remaining)}"
            )
            
            # Breathing/Pulse effect for the bar
            pulse = int((sim.time.time() % 2) * 10)
            bar = "━" * pulse + " " * (10 - pulse)
            
            # Summary of last run
            last_run_info = Table.grid(padding=(0, 2))
            last_run_info.add_row(
                f"Last Result: {'[green]PASSED[/green]' if summary.passed else '[red]FAILED[/red]'}",
                f"Points: {len(summary.results)}",
                f"Avg Resp: {summary.avg_response_ms:.0f}ms"
            )

            with Live(refresh_per_second=4) as live:
                live.update(Panel(
                    Group(status_text, last_run_info),
                    title="[bold blue]API Scanner[/bold blue]",
                    border_style="dim blue"
                ))
                await asyncio.sleep(0.25)
                if sim.time.time() - wait_start >= timing.wait_duration_seconds:
                    break

if __name__ == "__main__":
    try:
        timing = sim.parse_args()
        asyncio.run(run_example(timing))
    except KeyboardInterrupt:
        sys.exit(0)
