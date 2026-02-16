import asyncio
import sys
from rich.live import Live
from rich.panel import Panel
from rich.table import Table
from rich.console import Console, Group
from rich.text import Text

import scanner_sim as sim

# Metro line configuration
STATION_CHAR = "◉"
EMPTY_STATION = "○"
TRAIN_CHAR = "🚇"
LINE_CHAR = "─"

def get_status_color(status):
    """Get color for station based on status."""
    return {
        sim.EndpointStatus.OK: "green",
        sim.EndpointStatus.SLOW: "yellow",
        sim.EndpointStatus.TIMEOUT: "red",
        sim.EndpointStatus.ERROR: "magenta",
    }.get(status, "dim white")

def create_metro_map(results, total_expected, train_position=-1):
    """Create a metro/subway map visualization."""
    lines = []
    
    # Split endpoints into two lines for better layout
    line1_count = total_expected // 2
    line2_count = total_expected - line1_count
    
    # Line 1
    lines.append(Text("[bold cyan]Line 1[/bold cyan]"))
    line1_text = Text()
    for i in range(line1_count):
        # Add connection line
        if i > 0:
            line1_text.append(f" {LINE_CHAR*3} ", style="cyan")
        
        # Add station
        if i < len(results):
            r = results[i]
            color = get_status_color(r.status)
            station_name = r.endpoint.split('/')[-1][:4].upper()
            line1_text.append(f"{STATION_CHAR} ", style=color)
            line1_text.append(f"{station_name}", style=f"bold {color}")
        else:
            line1_text.append(f"{EMPTY_STATION} ", style="dim")
            if i < len(sim.ENDPOINTS):
                station_name = sim.ENDPOINTS[i].split('/')[-1][:4].upper()
                line1_text.append(f"{station_name}", style="dim")
        
        # Show train at position
        if train_position == i:
            line1_text.append(f" {TRAIN_CHAR}", style="bold cyan")
    
    lines.append(line1_text)
    lines.append(Text(""))
    
    # Line 2
    lines.append(Text("[bold magenta]Line 2[/bold magenta]"))
    line2_text = Text()
    for i in range(line2_count):
        idx = line1_count + i
        
        # Add connection line
        if i > 0:
            line2_text.append(f" {LINE_CHAR*3} ", style="magenta")
        
        # Add station
        if idx < len(results):
            r = results[idx]
            color = get_status_color(r.status)
            station_name = r.endpoint.split('/')[-1][:4].upper()
            line2_text.append(f"{STATION_CHAR} ", style=color)
            line2_text.append(f"{station_name}", style=f"bold {color}")
        else:
            line2_text.append(f"{EMPTY_STATION} ", style="dim")
            if idx < len(sim.ENDPOINTS):
                station_name = sim.ENDPOINTS[idx].split('/')[-1][:4].upper()
                line2_text.append(f"{station_name}", style="dim")
        
        # Show train at position
        if train_position == idx:
            line2_text.append(f" {TRAIN_CHAR}", style="bold magenta")
    
    lines.append(line2_text)
    
    # Create legend
    lines.append(Text(""))
    legend = Text()
    legend.append("■ ", style="green")
    legend.append("On-Time  ", style="dim")
    legend.append("■ ", style="yellow")
    legend.append("Delayed  ", style="dim")
    legend.append("■ ", style="red")
    legend.append("Failed  ", style="dim")
    lines.append(legend)
    
    return Group(*lines)

async def run_example(timing: sim.TimingConfig):
    console = Console()
    run_number = 1
    
    while True:
        results = []
        start_time = sim.time.time()
        
        with Live(refresh_per_second=10) as live:
            async for current, total, result in sim.simulate_scan(timing, run_number):
                results.append(result)
                
                header = Text.assemble(
                    ("🚇 ", "blue"), "METRO TRANSIT MONITOR ", ("• ", "dim"), f"RUN #{run_number}",
                    f" | {current}/{total} STATIONS"
                )
                
                # Stats panel
                stats = Table.grid(padding=(0, 3))
                stats.add_row(
                    f"[green]On-Time: {sum(1 for r in results if r.status == sim.EndpointStatus.OK)}[/green]",
                    f"[yellow]Delayed: {sum(1 for r in results if r.status == sim.EndpointStatus.SLOW)}[/yellow]",
                    f"[red]Failed: {sum(1 for r in results if r.status in [sim.EndpointStatus.ERROR, sim.EndpointStatus.TIMEOUT])}[/red]"
                )
                
                metro_map = create_metro_map(results, total, current - 1)
                
                live.update(Panel(
                    Group(header, Text(""), metro_map, Text(""), stats),
                    title="[bold]API Transit Network[/bold]",
                    border_style="blue",
                    padding=(1, 2)
                ))
        
        summary = sim.ScanSummary(run_number, results, start_time, sim.time.time())
        sim.notify_scan_complete(summary)
        run_number += 1
        
        # Idle State
        wait_start = sim.time.time()
        while sim.time.time() - wait_start < timing.wait_duration_seconds:
            remaining = timing.wait_duration_seconds - (sim.time.time() - wait_start)
            
            header = Text.assemble(
                ("● ", "green"), "SERVICE NORMAL ", ("• ", "dim"), f"NEXT DEPARTURE: {sim.format_duration(remaining)}"
            )
            
            # Show static map without train
            metro_map = create_metro_map(results, len(results), -1)
            
            # Service summary
            service_info = Table.grid(padding=(0, 2))
            service_status = "[green]ALL LINES OPERATIONAL[/green]" if summary.passed else "[red]⚠️  SERVICE DISRUPTION[/red]"
            service_info.add_row(
                service_status,
                f"Last check: {sim.format_time(summary.end_time)}",
                f"Avg response: {summary.avg_response_ms:.0f}ms"
            )
            
            with Live(refresh_per_second=2) as live:
                live.update(Panel(
                    Group(header, Text(""), metro_map, Text(""), service_info),
                    title="[bold]API Transit Network (Standby)[/bold]",
                    border_style="dim green",
                    padding=(1, 2)
                ))
                await asyncio.sleep(0.5)
                if sim.time.time() - wait_start >= timing.wait_duration_seconds:
                    break

if __name__ == "__main__":
    try:
        timing = sim.parse_args()
        asyncio.run(run_example(timing))
    except KeyboardInterrupt:
        sys.exit(0)
