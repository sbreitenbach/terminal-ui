import asyncio
import sys
import random
from rich.live import Live
from rich.panel import Panel
from rich.table import Table
from rich.console import Console, Group
from rich.text import Text
from rich.box import DOUBLE, ROUNDED

import scanner_sim as sim

# Circuit characters
IC_CHIP_TOP = "╔═══╗"
IC_CHIP_MID = "║ %s ║"
IC_CHIP_BOT = "╚═══╝"
TRACE_CHAR = "─"
SIGNAL_CHAR = "⚡"
LED_ON = "●"
LED_OFF = "○"

def get_chip_color(status):
    """Get color for circuit component based on status."""
    return {
        sim.EndpointStatus.OK: "green",
        sim.EndpointStatus.SLOW: "yellow",
        sim.EndpointStatus.TIMEOUT: "red",
        sim.EndpointStatus.ERROR: "magenta",
    }.get(status, "dim white")

def create_circuit_board(results, total_expected, signal_position=-1):
    """Create a circuit board visualization with IC chips and traces."""
    # Create a grid layout for the circuit
    table = Table.grid(expand=True, padding=(0, 1))
    
    # 3 columns of chips
    cols = 4
    for _ in range(cols):
        table.add_column(justify="center")
    
    # Build rows of IC chips
    num_rows = (total_expected + cols - 1) // cols
    
    for row_idx in range(num_rows):
        # Top of chips
        top_row = []
        mid_row = []
        bot_row = []
        trace_row = []
        
        for col_idx in range(cols):
            idx = row_idx * cols + col_idx
            
            if idx < len(results):
                r = results[idx]
                color = get_chip_color(r.status)
                chip_id = r.endpoint.split('/')[-1][:3].upper()
                
                # Add signal animation if scanning this chip
                signal_indicator = ""
                if signal_position == idx:
                    signal_indicator = f" {SIGNAL_CHAR}"
                
                top_row.append(f"[{color}]{IC_CHIP_TOP}[/{color}]{signal_indicator}")
                mid_row.append(f"[{color}]{IC_CHIP_MID % chip_id}[/{color}]")
                bot_row.append(f"[{color}]{IC_CHIP_BOT}[/{color}]")
                
                # Add trace connections between chips
                if col_idx < cols - 1 and idx < total_expected - 1:
                    trace_row.append(f"[dim blue]{TRACE_CHAR * 3}[/dim blue]")
                else:
                    trace_row.append("   ")
                    
            elif idx < total_expected:
                # Pending chip
                chip_id = sim.ENDPOINTS[idx].split('/')[-1][:3].upper() if idx < len(sim.ENDPOINTS) else "???"
                top_row.append(f"[dim]{IC_CHIP_TOP}[/dim]")
                mid_row.append(f"[dim]{IC_CHIP_MID % chip_id}[/dim]")
                bot_row.append(f"[dim]{IC_CHIP_BOT}[/dim]")
                
                if col_idx < cols - 1:
                    trace_row.append(f"[dim]{TRACE_CHAR * 3}[/dim]")
                else:
                    trace_row.append("   ")
            else:
                # Empty space
                top_row.append("     ")
                mid_row.append("     ")
                bot_row.append("     ")
                trace_row.append("   ")
        
        table.add_row(*top_row)
        table.add_row(*mid_row)
        table.add_row(*bot_row)
        
        # Add vertical spacing between rows
        if row_idx < num_rows - 1:
            spacing = []
            for col_idx in range(cols):
                spacing.append("[dim blue]  │  [/dim blue]")
            table.add_row(*spacing)
    
    return table

async def run_example(timing: sim.TimingConfig):
    console = Console()
    run_number = 1
    led_state = True
    
    while True:
        results = []
        start_time = sim.time.time()
        
        with Live(refresh_per_second=12) as live:
            async for current, total, result in sim.simulate_scan(timing, run_number):
                results.append(result)
                
                header = Text.assemble(
                    ("⚡ ", "blue"), "CIRCUIT BOARD TRACER ", ("• ", "dim"), f"RUN #{run_number}",
                    f" | {current}/{total} COMPONENTS"
                )
                
                # Power indicator
                power_led = LED_ON if led_state else LED_OFF
                led_state = not led_state
                power_status = Text.assemble(
                    "[bold]POWER:[/bold] ",
                    (f"{power_led}", "green"),
                    "  [bold]VOLTAGE:[/bold] 5.0V  [bold]CURRENT:[/bold] ",
                    (f"{50 + random.randint(-5, 5)}mA", "cyan")
                )
                
                circuit = create_circuit_board(results, total, current - 1)
                
                # Component stats
                stats = Table.grid(padding=(0, 3))
                stats.add_row(
                    f"[green]✓ Operational: {sum(1 for r in results if r.status == sim.EndpointStatus.OK)}[/green]",
                    f"[yellow]⚠ Slow: {sum(1 for r in results if r.status == sim.EndpointStatus.SLOW)}[/yellow]",
                    f"[red]✗ Failed: {sum(1 for r in results if r.status in [sim.EndpointStatus.ERROR, sim.EndpointStatus.TIMEOUT])}[/red]"
                )
                
                live.update(Panel(
                    Group(header, power_status, Text(""), circuit, Text(""), stats),
                    title="[bold]PCB Diagnostic System[/bold]",
                    border_style="blue",
                    box=DOUBLE,
                    padding=(1, 2)
                ))
        
        summary = sim.ScanSummary(run_number, results, start_time, sim.time.time())
        sim.notify_scan_complete(summary)
        run_number += 1
        
        # Idle State - blinking LED
        wait_start = sim.time.time()
        while sim.time.time() - wait_start < timing.wait_duration_seconds:
            remaining = timing.wait_duration_seconds - (sim.time.time() - wait_start)
            
            # Slow LED blink during idle
            led_blink = LED_ON if (int(sim.time.time() * 2) % 2) == 0 else LED_OFF
            
            header = Text.assemble(
                ("● ", "green"), "SYSTEM STANDBY ", ("• ", "dim"), f"NEXT SCAN: {sim.format_duration(remaining)}"
            )
            
            power_status = Text.assemble(
                "[bold]POWER:[/bold] ",
                (f"{led_blink}", "green"),
                "  [bold]STATUS:[/bold] ",
                ("[green]ALL SYSTEMS NOMINAL[/green]" if summary.passed else "[red]⚠️  FAULTS DETECTED[/red]")
            )
            
            circuit = create_circuit_board(results, len(results), -1)
            
            # System info
            sys_info = Table.grid(padding=(0, 2))
            sys_info.add_row(
                f"Last diagnostic: {sim.format_time(summary.end_time)}",
                f"Components: {len(results)}",
                f"Avg latency: {summary.avg_response_ms:.0f}ms"
            )
            
            with Live(refresh_per_second=4) as live:
                live.update(Panel(
                    Group(header, power_status, Text(""), circuit, Text(""), sys_info),
                    title="[bold]PCB Diagnostic System (Standby)[/bold]",
                    border_style="dim green",
                    box=ROUNDED,
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
