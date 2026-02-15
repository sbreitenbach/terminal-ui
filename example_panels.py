import asyncio
import sys
from rich.console import Console
from rich.layout import Layout
from rich.live import Live
from rich.panel import Panel
from rich.table import Table
from rich.text import Text
from rich.progress import Progress, BarColumn, TextColumn, SpinnerColumn
from rich.align import Align

import scanner_sim as sim

def make_layout() -> Layout:
    layout = Layout()
    layout.split_column(
        Layout(name="header", size=3),
        Layout(name="main"),
        Layout(name="footer", size=3),
    )
    layout["main"].split_row(
        Layout(name="left", ratio=1),
        Layout(name="center", ratio=2),
        Layout(name="right", ratio=1),
    )
    return layout

class StatsHeader:
    def __init__(self, run_number, start_time):
        self.run_number = run_number
        self.start_time = start_time

    def __rich__(self) -> Panel:
        grid = Table.grid(expand=True)
        grid.add_column(justify="left")
        grid.add_column(justify="center")
        grid.add_column(justify="right")
        grid.add_row(
            f"[bold blue]API SCANNER DASHBOARD[/bold blue]",
            f"Run: [white]#{self.run_number}[/white]",
            f"Started: [dim]{sim.format_time(self.start_time)}[/dim]"
        )
        return Panel(grid, style="white on blue")

async def run_example(timing: sim.TimingConfig):
    layout = make_layout()
    history = []
    run_number = 1
    
    while True:
        # --- Scanning State ---
        results = []
        start_time = sim.time.time()
        
        # Setup panels
        layout["header"].update(StatsHeader(run_number, start_time))
        
        with Live(layout, refresh_per_second=10):
            async for current, total, result in sim.simulate_scan(timing, run_number):
                results.append(result)
                
                # Center: Live Feed
                feed_table = Table(title="Live Endpoint Feed", box=None, expand=True)
                feed_table.add_column("S", width=1)
                feed_table.add_column("Endpoint")
                feed_table.add_column("Latency", justify="right")
                for r in results[-12:]:
                    feed_table.add_row(
                        sim.status_emoji(r.status),
                        f"[dim]{r.endpoint}[/dim]",
                        f"[bold cyan]{r.response_time_ms}ms[/bold cyan]"
                    )
                layout["center"].update(Panel(feed_table, border_style="cyan"))

                # Left: Status & Radar (Simulation)
                radar_frames = ["|", "/", "-", "\\"]
                frame = radar_frames[int(sim.time.time() * 4) % 4]
                radar_text = f"\n\n    {frame} SCANNING {frame}\n\n    {current}/{total}\n    Endpoints"
                layout["left"].update(Panel(Align.center(radar_text), title="Scanner Status", border_style="bold red"))

                # Right: Running Stats
                stats_table = Table.grid(padding=(1, 1))
                stats_table.add_row("Total:", str(len(results)))
                stats_table.add_row("Passed:", f"[green]{sum(1 for r in results if r.status == sim.EndpointStatus.OK)}[/green]")
                stats_table.add_row("Errors:", f"[red]{sum(1 for r in results if r.status == sim.EndpointStatus.ERROR)}[/red]")
                stats_table.add_row("Timeouts:", f"[magenta]{sum(1 for r in results if r.status == sim.EndpointStatus.TIMEOUT)}[/magenta]")
                layout["right"].update(Panel(stats_table, title="Current Run Stats", border_style="yellow"))

                # Footer: Progress
                progress = Progress(
                    TextColumn("{task.description}"),
                    BarColumn(bar_width=None),
                    TextColumn("[progress.percentage]{task.percentage:>3.0f}%"),
                )
                progress.add_task(f"Scanning {result.endpoint[:20]}...", total=total, completed=current)
                layout["footer"].update(Panel(progress, border_style="blue"))

        # Scan complete
        summary = sim.ScanSummary(run_number, results, start_time, sim.time.time())
        history.append(summary)
        sim.notify_scan_complete(summary)
        
        # --- Waiting State ---
        wait_start = sim.time.time()
        while sim.time.time() - wait_start < timing.wait_duration_seconds:
            remaining = timing.wait_duration_seconds - (sim.time.time() - wait_start)
            
            # Update Header for Idle
            layout["header"].update(Panel(
                Text.assemble(
                    ("● ", "green"), "IDLE ", ("Next scan in: ", "dim"), (sim.format_duration(remaining), "bold")
                ),
                style="white on black", border_style="dim white"
            ))

            # Left: Last Run Results
            res_color = "green" if summary.passed else "red"
            last_run_text = f"\nLast Run: [bold {res_color}]{'PASS' if summary.passed else 'FAIL'}[/bold {res_color}]\n\nAvg Latency:\n{summary.avg_response_ms:.1f}ms"
            layout["left"].update(Panel(Align.center(last_run_text), title="Last Result", border_style=res_color))

            # Center: Scan History
            history_table = Table(title="Scan History", box=None, expand=True)
            history_table.add_column("Run", justify="center")
            history_table.add_column("Result", justify="center")
            history_table.add_column("Points", justify="center")
            history_table.add_column("Avg Latency", justify="right")
            for h in history[-10:]:
                history_table.add_row(
                    f"#{h.run_number}",
                    f"[green]PASS[/green]" if h.passed else f"[red]FAIL[/red]",
                    str(len(h.results)),
                    f"{h.avg_response_ms:.0f}ms"
                )
            layout["center"].update(Panel(history_table, border_style="dim blue"))

            # Footer: Idle Bar
            layout["footer"].update(Panel(
                Align.center(f"Waiting for cycle... {sim.format_duration(remaining)} remaining"),
                border_style="dim blue"
            ))

            with Live(layout, refresh_per_second=4):
                await asyncio.sleep(0.5)
                if sim.time.time() - wait_start >= timing.wait_duration_seconds:
                    break
        
        run_number += 1

if __name__ == "__main__":
    try:
        timing = sim.parse_args()
        asyncio.run(run_example(timing))
    except KeyboardInterrupt:
        sys.exit(0)
