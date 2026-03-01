import asyncio
import sys
import random
from rich.live import Live
from rich.panel import Panel
from rich.table import Table
from rich.console import Console, Group
from rich.text import Text
from rich.box import DOUBLE, ROUNDED

import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', '..'))
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
    """Create a circuit board visualization with IC chips, traces, and LEDs."""
    table = Table.grid(expand=True, padding=(0, 1))
    
    # 4 columns of chips
    cols = 4
    for _ in range(cols):
        table.add_column(justify="center")
    
    num_rows = (total_expected + cols - 1) // cols
    
    for row_idx in range(num_rows):
        top_row = []
        mid_row = []
        bot_row = []
        led_row = []
        info_row = []
        
        for col_idx in range(cols):
            idx = row_idx * cols + col_idx
            
            if idx < len(results):
                r = results[idx]
                color = get_chip_color(r.status)
                chip_id = r.endpoint.split('/')[-1][:3].upper()
                
                # Signal indicator
                signal_indicator = ""
                if signal_position == idx:
                    signal_indicator = f" {SIGNAL_CHAR}"
                
                # LED indicator
                led_color = color
                led = LED_ON
                
                # Trace prefix (connects from left neighbor)
                trace_prefix = f"[dim blue]{TRACE_CHAR*2}[/dim blue]" if col_idx > 0 else "  "
                
                top_row.append(f"{trace_prefix}[{color}]{IC_CHIP_TOP}[/{color}]{signal_indicator}")
                mid_row.append(f"  [{color}]{IC_CHIP_MID % chip_id}[/{color}]")
                bot_row.append(f"  [{color}]{IC_CHIP_BOT}[/{color}]")
                led_row.append(f"  [{led_color}]{led}[/{led_color}] [{led_color}]{r.status.value[:3].upper()}[/{led_color}]")
                
                # Response time info
                ms_style = "green" if r.response_time_ms < 200 else "yellow" if r.response_time_ms < 1000 else "red"
                info_row.append(f"  [{ms_style}]{r.response_time_ms}ms[/{ms_style}]")
                    
            elif idx < total_expected:
                chip_id = sim.ENDPOINTS[idx].split('/')[-1][:3].upper() if idx < len(sim.ENDPOINTS) else "???"
                trace_prefix = f"[dim]{TRACE_CHAR*2}[/dim]" if col_idx > 0 else "  "
                top_row.append(f"{trace_prefix}[dim]{IC_CHIP_TOP}[/dim]")
                mid_row.append(f"  [dim]{IC_CHIP_MID % chip_id}[/dim]")
                bot_row.append(f"  [dim]{IC_CHIP_BOT}[/dim]")
                led_row.append(f"  [dim]{LED_OFF} ---[/dim]")
                info_row.append(f"  [dim]---[/dim]")
            else:
                top_row.append("       ")
                mid_row.append("       ")
                bot_row.append("       ")
                led_row.append("       ")
                info_row.append("       ")
        
        table.add_row(*top_row)
        table.add_row(*mid_row)
        table.add_row(*bot_row)
        table.add_row(*led_row)
        table.add_row(*info_row)
        
        # Vertical traces between rows
        if row_idx < num_rows - 1:
            spacing = []
            for col_idx in range(cols):
                spacing.append("[dim blue]  │  [/dim blue]")
            table.add_row(*spacing)
    
    return table

async def run_example(timing: sim.TimingConfig):
    console = Console()
    led_state = [True]
    
    def scanning_cb(run_number, current, total, result, results, start_time, history):
        header = Text.assemble(
            ("⚡ ", "blue"), "CIRCUIT BOARD TRACER ", ("• ", "dim"), f"RUN #{run_number}",
            f" | {current}/{total} COMPONENTS"
        )
        
        # Power indicator
        power_led = LED_ON if led_state[0] else LED_OFF
        led_state[0] = not led_state[0]
        power_status = Text.assemble(
            ("POWER: ", "bold"),
            (f"{power_led}", "green"),
            ("  VOLTAGE: ", "bold"), "5.0V",
            ("  CURRENT: ", "bold"),
            (f"{50 + random.randint(-5, 5)}mA", "cyan")
        )
        
        circuit = create_circuit_board(results, total, current - 1)
        
        # Component stats with legend
        stats = Table.grid(padding=(0, 3))
        stats.add_row(
            f"[green]✓ Operational: {sum(1 for r in results if r.status == sim.EndpointStatus.OK)}[/green]",
            f"[yellow]⚠ Slow: {sum(1 for r in results if r.status == sim.EndpointStatus.SLOW)}[/yellow]",
            f"[red]✗ Failed: {sum(1 for r in results if r.status in [sim.EndpointStatus.ERROR, sim.EndpointStatus.TIMEOUT])}[/red]"
        )
        
        legend = Text()
        legend.append("  ╔═══╗ ", style="dim")
        legend.append("IC Chip  ", style="dim")
        legend.append(f"{TRACE_CHAR*3} ", style="dim blue")
        legend.append("Trace  ", style="dim")
        legend.append(f"{LED_ON} ", style="green")
        legend.append("LED  ", style="dim")
        legend.append(f"{SIGNAL_CHAR} ", style="yellow")
        legend.append("Signal", style="dim")
        
        return Panel(
            Group(header, power_status, Text(""), circuit, Text(""), stats, legend),
            title="[bold]PCB Diagnostic System[/bold]",
            border_style="blue",
            box=DOUBLE,
            padding=(1, 2)
        )

    def idle_cb(remaining, summary, history, wait_start):
        # Slow LED blink during idle
        led_blink = LED_ON if (int(sim.time.time() * 2) % 2) == 0 else LED_OFF
        
        header = Text.assemble(
            ("● ", "green"), "SYSTEM STANDBY ", ("• ", "dim"), f"NEXT SCAN: {sim.format_duration(remaining)}"
        )
        
        power_status = Text.assemble(
            ("POWER: ", "bold"),
            (f"{led_blink}", "green"),
            ("  STATUS: ", "bold"),
            (Text.from_markup("[green]ALL SYSTEMS NOMINAL[/green]" if summary.passed else "[red]⚠️  FAULTS DETECTED[/red]"))
        )
        
        circuit = create_circuit_board(summary.results, len(summary.results), -1)
        
        # System info
        sys_info = Table.grid(padding=(0, 2))
        sys_info.add_row(
            f"Last diagnostic: {sim.format_time(summary.end_time)}",
            f"Components: {len(summary.results)}",
            f"Avg latency: {summary.avg_response_ms:.0f}ms"
        )
        
        return Panel(
            Group(header, power_status, Text(""), circuit, Text(""), sys_info),
            title="[bold]PCB Diagnostic System (Standby)[/bold]",
            border_style="dim green",
            box=ROUNDED,
            padding=(1, 2)
        )

    await sim.run_app(
        timing,
        scanning_callback=scanning_cb,
        idle_callback=idle_cb,
        console=console,
        scan_fps=12,
        idle_fps=4
    )

if __name__ == "__main__":
    try:
        timing = sim.parse_args()
        asyncio.run(run_example(timing))
    except KeyboardInterrupt:
        sys.exit(0)
