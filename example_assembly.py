import asyncio
import sys
from rich.live import Live
from rich.panel import Panel
from rich.console import Console, Group
from rich.text import Text
from rich.table import Table
from rich.align import Align

import scanner_sim as sim

BELT_WIDTH = 60

def draw_assembly_line(results, total_expected, offset_tick):
    # Determine the "active" item (the one currently being scanned)
    # We'll simulate a belt moving to the right
    # [ INBOX ] ==(belt)==> [ SCANNER ] ==(belt)==> [ OUTBOX ]
    
    # We can just show the latest 5 results moving across the belt.
    belt_view = Table.grid(padding=(0,2))
    
    lines = []
    
    # Draw top of machinery
    machinery_top = Text("    ┌" + "─"*(BELT_WIDTH-10) + "┐    ", style="dim black")
    lines.append(machinery_top)

    # The actual items on the belt
    belt_content = []
    # Pad items to create movement effect
    visible_items = results[-5:]
    
    belt_str = ""
    for r in visible_items:
        color = "green"
        icon = "✓"
        if r.status == sim.EndpointStatus.SLOW: 
            color = "yellow"
            icon = "⚠"
        elif r.status != sim.EndpointStatus.OK:
            color = "red"
            icon = "✖"
            
        short_name = r.endpoint.split("/")[-1][:6]
        belt_str += f"[{color}][ {icon} {short_name} ][/{color}]  "
        
    # Animate the belt moving based on offset_tick
    anim_char = ["=", "≡", "-", "≈"][offset_tick % 4]
    
    belt_line = Text.from_markup(" 📥  " + belt_str.rjust(BELT_WIDTH-12) + "  📦 " )
    lines.append(belt_line)
    
    # Draw bottom of machinery
    machinery_bot = Text("    └" + anim_char*(BELT_WIDTH-10) + "┘    ", style="dim black")
    lines.append(machinery_bot)
    
    # Stats row
    ok = sum(1 for r in results if r.status == sim.EndpointStatus.OK)
    issues = sum(1 for r in results if r.status != sim.EndpointStatus.OK)
    stats_line = Text.assemble(
        ("Production line: ", "dim"),
        (f"{ok} PASS", "bold green"), " | ",
        (f"{issues} REJECTED", "bold red" if issues > 0 else "dim")
    )
    lines.append(Text(""))
    lines.append(Align.center(stats_line))
    
    return Group(*lines)

async def run_example(timing: sim.TimingConfig):
    console = Console()
    tick = [0]
    
    def scanning_cb(run_number, current, total, result, results, start_time, history):
        tick[0] += 1
        
        header = Text.assemble(
            ("🏭 ", "yellow"), "ASSEMBLY LINE ", ("• ", "dim"), f"SHIFT #{run_number}",
            f"   Processed: {current}/{total}"
        )
        
        factory_view = draw_assembly_line(results, total, tick[0])

        return Panel(
            Group(header, Text(""), Align.center(factory_view)),
            title="[bold]Industrial API Processor[/bold]",
            border_style="yellow",
            padding=(1, 2)
        )

    def idle_cb(remaining, summary, history, wait_start):
        tick[0] += 1
        
        header = Text.assemble(
            ("● ", "green"), "MAINTENANCE MODE ", ("• ", "dim"), f"NEXT SHIFT: {sim.format_duration(remaining)}"
        )
        
        factory_view = draw_assembly_line(summary.results, len(summary.results), 0)
        
        return Panel(
            Group(header, Text(""), Align.center(factory_view)),
            title="[bold]Industrial API Processor (Standby)[/bold]",
            border_style="dim green",
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
