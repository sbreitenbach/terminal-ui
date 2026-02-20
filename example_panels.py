import asyncio
import sys
from rich.console import Console, Group
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
    def __init__(self, run_number, start_time, current=0, total=0):
        self.run_number = run_number
        self.start_time = start_time
        self.current = current
        self.total = total

    def __rich__(self) -> Panel:
        grid = Table.grid(expand=True)
        grid.add_column(justify="left")
        grid.add_column(justify="center")
        grid.add_column(justify="right")
        pct = f"{self.current/self.total*100:.0f}%" if self.total else "0%"
        grid.add_row(
            f"[bold blue]API SCANNER DASHBOARD[/bold blue]",
            f"Run: [black]#{self.run_number}[/black]  ·  {self.current}/{self.total} ({pct})",
            f"Started: [dim]{sim.format_time(self.start_time)}[/dim]"
        )
        return Panel(grid, style="black on white", border_style="blue")

async def run_example(timing: sim.TimingConfig):
    layout = make_layout()
    
    def scanning_cb(run_number, current, total, result, results, start_time, history):
        # Header with scan progress
        layout["header"].update(StatsHeader(run_number, start_time, current, total))
        
        # Center: Live Feed with column headers
        feed_table = Table(title="Live Endpoint Feed", box=None, expand=True, show_header=True, header_style="dim")
        feed_table.add_column("S", width=2)
        feed_table.add_column("Method", width=5)
        feed_table.add_column("Endpoint")
        feed_table.add_column("Code", justify="right", width=4)
        feed_table.add_column("Latency", justify="right")
        for r in results[-12:]:
            ms_style = "green" if r.response_time_ms < 200 else "yellow" if r.response_time_ms < 1000 else "red"
            feed_table.add_row(
                sim.status_emoji(r.status),
                Text(r.method, style="dim cyan"),
                f"[dim]{r.endpoint}[/dim]",
                Text(str(r.status_code) if r.status_code else "---", style="dim"),
                f"[bold {ms_style}]{r.response_time_ms}ms[/bold {ms_style}]"
            )
        layout["center"].update(Panel(feed_table, border_style="blue"))

        # Left: Animated spinner + stats
        ok = sum(1 for r in results if r.status == sim.EndpointStatus.OK)
        fail = sum(1 for r in results if r.status in (sim.EndpointStatus.ERROR, sim.EndpointStatus.TIMEOUT))
        slow = sum(1 for r in results if r.status == sim.EndpointStatus.SLOW)
        avg = sum(r.response_time_ms for r in results) / len(results) if results else 0

        spinner_frames = ["⠋", "⠙", "⠹", "⠸", "⠼", "⠴", "⠦", "⠧", "⠇", "⠏"]
        frame = spinner_frames[int(sim.time.time() * 10) % len(spinner_frames)]
        
        scanner_text = Text()
        scanner_text.append(f"\n  {frame} ", style="bold bright_red")
        scanner_text.append("SCANNING\n\n", style="bold bright_red")
        scanner_text.append(f"  {current}/{total}\n", style="bold")
        scanner_text.append(f"  Endpoints\n\n", style="dim")
        scanner_text.append(f"  Avg: {avg:.0f}ms\n", style="blue")
        
        layout["left"].update(Panel(scanner_text, title="Scanner Status", border_style="bold red"))

        # Right: Running Stats + history preview
        stats_table = Table.grid(padding=(1, 1))
        stats_table.add_row("OK:", f"[green]{ok}[/green]")
        stats_table.add_row("Slow:", f"[yellow]{slow}[/yellow]")
        stats_table.add_row("Errors:", f"[red]{fail}[/red]")
        
        # Show recent history during scanning
        if history:
            stats_table.add_row("", "")
            stats_table.add_row("[dim]─── History ───[/dim]", "")
            for h in history[-3:]:
                rc = "green" if h.passed else "red"
                stats_table.add_row(
                    f"Run #{h.run_number}:",
                    f"[{rc}]{'PASS' if h.passed else 'FAIL'}[/{rc}]"
                )
            
        layout["right"].update(Panel(stats_table, title="Current Run Stats", border_style="yellow"))

        # Footer: Progress
        progress = Progress(
            SpinnerColumn(),
            TextColumn("{task.description}"),
            BarColumn(bar_width=None),
            TextColumn("[progress.percentage]{task.percentage:>3.0f}%"),
        )
        ep_short = result.endpoint.split("/")[-1]
        progress.add_task(f"Scanning {ep_short}...", total=total, completed=current)
        layout["footer"].update(Panel(progress, border_style="blue"))

    def idle_cb(remaining, summary, history, wait_start):
        # Update Header for Idle
        layout["header"].update(Panel(
            Text.assemble(
                ("● ", "green"), "IDLE ", ("Next scan in: ", "dim"), (sim.format_duration(remaining), "bold")
            ),
            style="black on white", border_style="dim blue"
        ))

        # Left: Last Run Results
        res_color = "green" if summary.passed else "red"
        last_run_text = f"\nLast Run: [bold {res_color}]{'PASS' if summary.passed else 'FAIL'}[/bold {res_color}]\n\nAvg Latency:\n{summary.avg_response_ms:.1f}ms"
        layout["left"].update(Panel(Align.center(last_run_text), title="Last Result", border_style=res_color))

        # Center: Scan History
        history_table = Table(title="Scan History", box=None, expand=True, show_header=True, header_style="dim")
        history_table.add_column("Run", justify="center")
        history_table.add_column("Result", justify="center")
        history_table.add_column("OK", justify="center")
        history_table.add_column("Fail", justify="center")
        history_table.add_column("Avg Latency", justify="right")
        for h in history[-10:]:
            rc = "green" if h.passed else "red"
            history_table.add_row(
                f"#{h.run_number}",
                f"[{rc}]{'PASS' if h.passed else 'FAIL'}[/{rc}]",
                f"[green]{h.total_ok}[/green]",
                f"[red]{h.total_errors + h.total_timeouts}[/red]",
                f"{h.avg_response_ms:.0f}ms"
            )
        layout["center"].update(Panel(history_table, border_style="dim blue"))

        # Footer: Idle Bar
        layout["footer"].update(Panel(
            Align.center(f"Waiting for cycle... {sim.format_duration(remaining)} remaining"),
            border_style="dim blue"
        ))

    await sim.run_app(
        timing,
        scanning_callback=scanning_cb,
        idle_callback=idle_cb,
        base_renderable=layout,
        scan_fps=10,
        idle_fps=4
    )

if __name__ == "__main__":
    try:
        timing = sim.parse_args()
        asyncio.run(run_example(timing))
    except KeyboardInterrupt:
        sys.exit(0)
