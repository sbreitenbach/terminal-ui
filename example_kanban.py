import asyncio
import sys
from rich.live import Live
from rich.panel import Panel
from rich.console import Console, Group
from rich.text import Text
from rich.table import Table
from rich.columns import Columns

import scanner_sim as sim

def create_card(result: sim.EndpointResult) -> Panel:
    """Create a Kanban card for a scanned endpoint."""
    ms_style = "green" if result.response_time_ms < 200 else "yellow" if result.response_time_ms < 1000 else "red"
    border = "green" if result.status == sim.EndpointStatus.OK else "yellow" if result.status == sim.EndpointStatus.SLOW else "red"
    
    short_ep = "/".join(result.endpoint.split("/")[-2:])
    
    content = Text.assemble(
        (f"{result.method} ", "cyan"),
        (short_ep, "bold"),
        "\n",
        (f"{result.response_time_ms}ms", ms_style),
        " | ",
        (f"{result.status_code or '---'}", "dim")
    )
    
    return Panel(content, border_style=border, width=30)

async def run_example(timing: sim.TimingConfig):
    console = Console()
    
    def scanning_cb(run_number, current, total, result, results, start_time, history):
        header = Text.assemble(
            ("📋 ", "blue"), "KANBAN BOARD ", ("• ", "dim"), f"SPRINT #{run_number}",
            f" | Tickets: {current}/{total}"
        )
        
        # Categorize results
        ok_cards = []
        slow_cards = []
        fail_cards = []
        
        for r in results:
            if r.status == sim.EndpointStatus.OK:
                ok_cards.append(create_card(r))
            elif r.status == sim.EndpointStatus.SLOW:
                slow_cards.append(create_card(r))
            else:
                fail_cards.append(create_card(r))
                
        # Calculate pending
        pending_count = total - current
        pending_panel = Panel(
            Text(f"\n      {pending_count} tickets\n      in backlog...", style="dim italic"),
            title="[dim]To Do[/dim]",
            border_style="dim",
            width=32,
            height=6
        ) if pending_count > 0 else None
        
        # Build columns
        cols = [
            Group(Panel("[bold]To Do[/bold]", border_style="dim", width=32), pending_panel) if pending_panel else Group(Panel("[bold]To Do[/bold]", border_style="dim", width=32)),
            Group(Panel("[bold green]Done (OK)[/bold green]", border_style="green", width=32), *ok_cards[-5:]),
            Group(Panel("[bold yellow]Review (Slow)[/bold yellow]", border_style="yellow", width=32), *slow_cards[-5:]),
            Group(Panel("[bold red]Blocked (Fail)[/bold red]", border_style="red", width=32), *fail_cards[-5:])
        ]
        
        board = Columns(cols, padding=(0, 2))
        
        # Summary footer
        footer = Text(f"Latest activity: Processed {result.method} {result.endpoint} smoothly.", style="dim")
        if result.status != sim.EndpointStatus.OK:
            footer = Text(f"Latest activity: Issue detected with {result.endpoint}.", style="yellow")
            
        return Panel(
            Group(header, Text(""), board, Text(""), footer),
            title="[bold]Sprint Dashboard[/bold]",
            border_style="blue",
            padding=(1, 2)
        )

    def idle_cb(remaining, summary, history, wait_start):
        header = Text.assemble(
            ("☕ ", "green"), "SPRINT RETROSPECTIVE ", ("• ", "dim"), f"NEXT PLANNING: {sim.format_duration(remaining)}"
        )
        
        # Categorize all results from summary
        ok_count = sum(1 for r in summary.results if r.status == sim.EndpointStatus.OK)
        slow_count = sum(1 for r in summary.results if r.status == sim.EndpointStatus.SLOW)
        fail_count = sum(1 for r in summary.results if r.status in [sim.EndpointStatus.ERROR, sim.EndpointStatus.TIMEOUT])
        
        summary_table = Table.grid(padding=(1, 5))
        summary_table.add_row(
            Panel(f"\n[green]{ok_count}[/green]\nTickets Done", title="[bold green]Done[/bold green]", border_style="green", width=25, height=5, expand=True),
            Panel(f"\n[yellow]{slow_count}[/yellow]\nTickets Needs Review", title="[bold yellow]Review[/bold yellow]", border_style="yellow", width=25, height=5, expand=True),
            Panel(f"\n[red]{fail_count}[/red]\nTickets Blocked", title="[bold red]Blocked[/bold red]", border_style="red", width=25, height=5, expand=True)
        )
        
        msg = f"[bold green]Sprint met all objectives! Avg resolution: {summary.avg_response_ms:.0f}ms[/bold green]"
        if not summary.passed:
            msg = f"[bold red]Sprint missed targets. {summary.total_errors + summary.total_timeouts} tickets rolled over.[/bold red]"
            
        return Panel(
            Group(header, Text(""), summary_table, Text(""), Text.from_markup(msg)),
            title="[bold]Sprint Dashboard (Idle)[/bold]",
            border_style="dim green",
            padding=(1, 2)
        )

    await sim.run_app(
        timing,
        scanning_callback=scanning_cb,
        idle_callback=idle_cb,
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
