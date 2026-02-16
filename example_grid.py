import asyncio
import sys
from rich.live import Live
from rich.panel import Panel
from rich.table import Table
from rich.console import Console, Group
from rich.text import Text
from rich.style import Style

import scanner_sim as sim

def get_grid_color(status: sim.EndpointStatus):
    return {
        sim.EndpointStatus.OK: "green",
        sim.EndpointStatus.SLOW: "yellow",
        sim.EndpointStatus.TIMEOUT: "red",
        sim.EndpointStatus.ERROR: "magenta",
    }.get(status, "dim white")

def create_grid(results, total_expected):
    table = Table.grid(expand=True, padding=(1, 1))
    # We want a 4x3 grid for the 12 endpoints
    cols = 4
    for _ in range(cols):
        table.add_column(justify="center")

    rows = []
    for i in range(0, total_expected, cols):
        row_cells = []
        for j in range(cols):
            idx = i + j
            if idx < len(results):
                r = results[idx]
                color = get_grid_color(r.status)
                cell_content = Text.assemble(
                    (sim.status_emoji(r.status), color),
                    f"\n{r.endpoint.split('/')[-1]}\n",
                    (f"{r.response_time_ms}ms", "dim")
                )
                row_cells.append(Panel(cell_content, border_style=color, expand=True))
            elif idx < total_expected:
                # Placeholder for pending endpoints
                row_cells.append(Panel(Text("PENDING", style="dim"), border_style="dim", expand=True))
        table.add_row(*row_cells)
    return table

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
                    ("■ ", "blue"), "GRID SCANNER ", ("• ", "dim"), f"RUN #{run_number}",
                    f" | {current}/{total} COMPLETED"
                )
                
                grid = create_grid(results, total)
                
                live.update(Panel(
                    Group(header, Text(""), grid),
                    title="[bold]Endpoint Matrix[/bold]",
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
                ("● ", "green"), "SYSTEM READY ", ("• ", "dim"), f"NEXT SCAN: {sim.format_duration(remaining)}"
            )
            
            grid = create_grid(results, len(results))
            
            with Live(refresh_per_second=4) as live:
                live.update(Panel(
                    Group(header, Text(""), grid),
                    title="[bold]Endpoint Matrix (Idle)[/bold]",
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
