import asyncio
import sys
import math
from rich.live import Live
from rich.panel import Panel
from rich.table import Table
from rich.console import Console, Group
from rich.text import Text

import scanner_sim as sim

# Wave/spectrum constants
SPECTRUM_HEIGHT = 15
BAR_WIDTH = 5

def get_bar_height(response_time_ms, status):
    """Calculate bar height based on response time, with max for errors."""
    if status in [sim.EndpointStatus.ERROR, sim.EndpointStatus.TIMEOUT]:
        return SPECTRUM_HEIGHT
    # Map response times to bar heights (0-2500ms -> 1-15 bars)
    normalized = min(response_time_ms / 2500.0, 1.0)
    return max(1, int(normalized * SPECTRUM_HEIGHT))

def get_bar_color(status):
    """Get color for the bar based on status."""
    return {
        sim.EndpointStatus.OK: "green",
        sim.EndpointStatus.SLOW: "yellow",
        sim.EndpointStatus.TIMEOUT: "red",
        sim.EndpointStatus.ERROR: "magenta",
    }.get(status, "dim white")

def create_spectrum(results, total_expected, pulse_offset=0):
    """Create a spectrum analyzer visualization with vertical bars."""
    table = Table.grid(expand=False, padding=(0, 0))
    
    # Add columns for each endpoint
    num_bars = total_expected
    for _ in range(num_bars):
        table.add_column(justify="center", width=BAR_WIDTH)
    
    # Build the spectrum from top to bottom
    rows = []
    for height_level in range(SPECTRUM_HEIGHT, 0, -1):
        row_cells = []
        for i in range(num_bars):
            if i < len(results):
                r = results[i]
                bar_height = get_bar_height(r.response_time_ms, r.status)
                color = get_bar_color(r.status)
                
                # Add pulse effect during scanning
                if pulse_offset > 0:
                    pulse_intensity = (pulse_offset + i) % 3
                    if pulse_intensity == 0:
                        bar_height = min(SPECTRUM_HEIGHT, bar_height + 2)
                
                if height_level <= bar_height:
                    # Use filled blocks for the bar
                    if height_level == bar_height:
                        cell = f"[{color}]▀▀▀[/{color}]"
                    else:
                        cell = f"[{color}]███[/{color}]"
                else:
                    cell = "[dim]···[/dim]"
            else:
                # Pending endpoint - show dim placeholder
                if height_level == 1:
                    cell = "[dim]▁▁▁[/dim]"
                else:
                    cell = "   "
            row_cells.append(cell)
        rows.append(row_cells)
    
    # Add all rows to table
    for row in rows:
        table.add_row(*row)
    
    # Add endpoint labels at bottom
    label_row = []
    for i in range(num_bars):
        if i < len(sim.ENDPOINTS):
            ep_name = sim.ENDPOINTS[i].split('/')[-1][:3].upper()
            if i < len(results):
                color = get_bar_color(results[i].status)
                label_row.append(f"[{color}]{ep_name}[/{color}]")
            else:
                label_row.append(f"[dim]{ep_name}[/dim]")
        else:
            label_row.append("   ")
    table.add_row(*label_row)
    
    return table

async def run_example(timing: sim.TimingConfig):
    console = Console()
    run_number = 1
    pulse_counter = 0
    
    while True:
        results = []
        start_time = sim.time.time()
        
        with Live(refresh_per_second=12) as live:
            async for current, total, result in sim.simulate_scan(timing, run_number):
                results.append(result)
                pulse_counter += 1
                
                header = Text.assemble(
                    ("♪ ", "blue"), "SPECTRUM ANALYZER ", ("• ", "dim"), f"RUN #{run_number}",
                    f" | {current}/{total} SCANNED"
                )
                
                # Stats summary
                stats = Table.grid(padding=(0, 2))
                stats.add_row(
                    f"[green]OK: {sum(1 for r in results if r.status == sim.EndpointStatus.OK)}[/green]",
                    f"[yellow]SLOW: {sum(1 for r in results if r.status == sim.EndpointStatus.SLOW)}[/yellow]",
                    f"[red]FAIL: {sum(1 for r in results if r.status in [sim.EndpointStatus.ERROR, sim.EndpointStatus.TIMEOUT])}[/red]",
                    f"[blue]AVG: {(sum(r.response_time_ms for r in results)/len(results)):.0f}ms[/blue]" if results else "[blue]AVG: --[/blue]"
                )
                
                spectrum = create_spectrum(results, total, pulse_counter)
                
                live.update(Panel(
                    Group(header, Text(""), spectrum, Text(""), stats),
                    title="[bold]Audio Waveform Monitor[/bold]",
                    border_style="blue",
                    padding=(1, 2)
                ))
        
        summary = sim.ScanSummary(run_number, results, start_time, sim.time.time())
        sim.notify_scan_complete(summary)
        run_number += 1
        
        # Idle State - gentle oscillation
        wait_start = sim.time.time()
        while sim.time.time() - wait_start < timing.wait_duration_seconds:
            remaining = timing.wait_duration_seconds - (sim.time.time() - wait_start)
            
            header = Text.assemble(
                ("● ", "green"), "MONITORING ", ("• ", "dim"), f"NEXT SCAN: {sim.format_duration(remaining)}"
            )
            
            # Create breathing effect by gently modulating bar heights
            breathing_phase = (sim.time.time() % 3.0) / 3.0  # 0 to 1 cycle
            breathing_offset = int(math.sin(breathing_phase * 2 * math.pi) * 2)
            
            # Modify results slightly for breathing effect
            breathing_results = []
            for r in results:
                modified_result = sim.EndpointResult(
                    endpoint=r.endpoint,
                    status=r.status,
                    response_time_ms=max(30, r.response_time_ms + breathing_offset * 50),
                    status_code=r.status_code,
                    timestamp=r.timestamp
                )
                breathing_results.append(modified_result)
            
            spectrum = create_spectrum(breathing_results, len(results), 0)
            
            stats = Table.grid(padding=(0, 2))
            stats_text = f"Last scan: {'[green]PASSED[/green]' if summary.passed else '[red]FAILED[/red]'}"
            stats_text += f" | {len(results)} endpoints | Avg {summary.avg_response_ms:.0f}ms"
            stats.add_row(stats_text)
            
            with Live(refresh_per_second=4) as live:
                live.update(Panel(
                    Group(header, Text(""), spectrum, Text(""), stats),
                    title="[bold]Audio Waveform Monitor (Idle)[/bold]",
                    border_style="dim green",
                    padding=(1, 2)
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
