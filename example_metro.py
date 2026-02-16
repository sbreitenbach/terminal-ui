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

# 4 colored lines with 3 endpoints each
LINE_CONFIGS = [
    {"name": "Line A", "color": "cyan",    "indices": [0, 1, 2]},
    {"name": "Line B", "color": "magenta", "indices": [3, 4, 5]},
    {"name": "Line C", "color": "blue",    "indices": [6, 7, 8]},
    {"name": "Line D", "color": "yellow",  "indices": [9, 10, 11]},
]

# Transfer stations: where two lines intersect (shared endpoints)
TRANSFERS = {
    2: 3,   # Line A station 2 connects to Line B station 0
    5: 6,   # Line B station 2 connects to Line C station 0
    8: 9,   # Line C station 2 connects to Line D station 0
}

def get_status_color(status):
    return {
        sim.EndpointStatus.OK: "green",
        sim.EndpointStatus.SLOW: "yellow",
        sim.EndpointStatus.TIMEOUT: "red",
        sim.EndpointStatus.ERROR: "magenta",
    }.get(status, "dim white")

def create_metro_map(results, total_expected, train_position=-1):
    """Create a metro/subway map with 4 colored lines, transfer points, and response times."""
    lines_group = []
    
    for lc in LINE_CONFIGS:
        line_color = lc["color"]
        indices = lc["indices"]
        
        # Line label
        lines_group.append(Text(f"[bold {line_color}]{lc['name']}[/bold {line_color}]"))
        
        line_text = Text()
        for pos, idx in enumerate(indices):
            # Connection line between stations
            if pos > 0:
                line_text.append(f" {LINE_CHAR*3} ", style=line_color)
            
            # Station marker
            if idx < len(results):
                r = results[idx]
                color = get_status_color(r.status)
                station_name = r.endpoint.split('/')[-1][:4].upper()
                line_text.append(f"{STATION_CHAR} ", style=color)
                line_text.append(station_name, style=f"bold {color}")
                # Show response time at the station
                ms_style = "green" if r.response_time_ms < 200 else "yellow" if r.response_time_ms < 1000 else "red"
                line_text.append(f"({r.response_time_ms}ms)", style=f"dim {ms_style}")
            else:
                line_text.append(f"{EMPTY_STATION} ", style="dim")
                if idx < len(sim.ENDPOINTS):
                    station_name = sim.ENDPOINTS[idx].split('/')[-1][:4].upper()
                    line_text.append(station_name, style="dim")
            
            # Show train at this position
            if train_position == idx:
                line_text.append(f" {TRAIN_CHAR}", style=f"bold {line_color}")
        
        lines_group.append(line_text)
        
        # Transfer marker between lines
        if indices[-1] in TRANSFERS:
            transfer_text = Text()
            transfer_text.append("            ↕ ", style="dim")
            transfer_text.append("TRANSFER", style="dim bold")
            lines_group.append(transfer_text)
        else:
            lines_group.append(Text(""))
    
    # Legend
    legend = Text()
    legend.append("■ ", style="green")
    legend.append("On-Time  ", style="dim")
    legend.append("■ ", style="yellow")
    legend.append("Delayed  ", style="dim")
    legend.append("■ ", style="red")
    legend.append("Failed  ", style="dim")
    legend.append("  ↕ Transfer  ", style="dim")
    for lc in LINE_CONFIGS:
        legend.append(f"━ {lc['name']}  ", style=lc["color"])
    lines_group.append(legend)
    
    return Group(*lines_group)

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
                ok = sum(1 for r in results if r.status == sim.EndpointStatus.OK)
                slow = sum(1 for r in results if r.status == sim.EndpointStatus.SLOW)
                fail = sum(1 for r in results if r.status in [sim.EndpointStatus.ERROR, sim.EndpointStatus.TIMEOUT])
                avg = sum(r.response_time_ms for r in results) / len(results) if results else 0
                stats = Table.grid(padding=(0, 3))
                stats.add_row(
                    f"[green]On-Time: {ok}[/green]",
                    f"[yellow]Delayed: {slow}[/yellow]",
                    f"[red]Failed: {fail}[/red]",
                    f"[blue]Avg: {avg:.0f}ms[/blue]"
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
