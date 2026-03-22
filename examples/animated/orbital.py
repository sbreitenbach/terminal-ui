import asyncio
import sys
import math
from rich.live import Live
from rich.panel import Panel
from rich.console import Console, Group
from rich.text import Text
from rich.table import Table

import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', '..'))
import scanner_sim as sim

# Orbital constants
RADIUS = 12
CENTER = (25, 12)
WIDTH = 50
HEIGHT = 25

def get_orbital_map(results, total_expected, rotation_offset):
    canvas = [[" " for _ in range(WIDTH)] for _ in range(HEIGHT)]
    
    # Draw core server at center
    core_text = "CORE"
    for i, char in enumerate(core_text):
        if 0 <= CENTER[0]-2+i < WIDTH and 0 <= CENTER[1] < HEIGHT:
            canvas[CENTER[1]][CENTER[0]-2+i] = (f"[bold cyan]{char}[/bold cyan]")
    
    if 0 <= CENTER[0] < WIDTH and 0 <= CENTER[1]-1 < HEIGHT:
        canvas[CENTER[1]-1][CENTER[0]] = ("[bold cyan]▲[/bold cyan]")
    if 0 <= CENTER[0] < WIDTH and 0 <= CENTER[1]+1 < HEIGHT:
        canvas[CENTER[1]+1][CENTER[0]] = ("[bold cyan]▼[/bold cyan]")

    # Draw orbits (dim rings)
    for y in range(HEIGHT):
        for x in range(WIDTH):
            dx = x - CENTER[0]
            dy = (y - CENTER[1]) * 2  # Adjust for terminal character aspect ratio
            dist = math.sqrt(dx*dx + dy*dy)
            
            if canvas[y][x] == " ":
                if abs(dist - RADIUS) < 0.5:
                    canvas[y][x] = "[dim blue]·[/dim blue]"
                elif abs(dist - (RADIUS + 6)) < 0.5: # Outer lag orbit
                    canvas[y][x] = "[dim magenta]·[/dim magenta]"

    # Place endpoints
    for i in range(total_expected):
        base_angle = (i / total_expected) * 360 + rotation_offset
        a_rad = math.radians(base_angle)
        
        # Determine orbit distance and style based on status
        current_radius = RADIUS
        status_char = "○"
        status_color = "dim"
        
        if i < len(results):
            r = results[i]
            if r.status == sim.EndpointStatus.OK:
                status_char = "●"
                status_color = "green"
            elif r.status == sim.EndpointStatus.SLOW:
                status_char = "●"
                status_color = "yellow"
                current_radius = RADIUS + 6  # Pushed to outer lag orbit
                a_rad = math.radians(base_angle - 15) # Dragging behind
            else:
                status_char = "✖"
                status_color = "red"
                # Broken orbit (floating away)
                current_radius = RADIUS + 10 + (results.index(r) % 5)
                a_rad = math.radians(base_angle + 45)

        x = int(CENTER[0] + current_radius * math.cos(a_rad))
        y = int(CENTER[1] + current_radius * math.sin(a_rad) / 2)
        
        if 0 <= x < WIDTH and 0 <= y < HEIGHT:
            canvas[y][x] = f"[{status_color}]{status_char}[/{status_color}]"

    # Convert canvas to text
    lines = []
    for row in canvas:
        line = Text()
        for cell in row:
            if cell.startswith("["):
                line.append_text(Text.from_markup(cell))
            else:
                line.append(cell)
        lines.append(line)
        
    return Group(*lines)


async def run_example(timing: sim.TimingConfig):
    console = Console()
    rotation = [0]
    
    def scanning_cb(run_number, current, total, result, results, start_time, history):
        rotation[0] = (rotation[0] + 2) % 360
        
        header = Text.assemble(
            ("🪐 ", "cyan"), "ORBITAL MAP ", ("• ", "dim"), f"RUN #{run_number}",
            f"   SYNC: {int(current/total*100)}%"
        )
        
        orbital_view = get_orbital_map(results, total, rotation[0])
        
        # Legend/Stats
        stats = Table.grid(padding=(0, 3))
        ok = sum(1 for r in results if r.status == sim.EndpointStatus.OK)
        slow = sum(1 for r in results if r.status == sim.EndpointStatus.SLOW)
        fail = sum(1 for r in results if r.status in [sim.EndpointStatus.ERROR, sim.EndpointStatus.TIMEOUT])
        stats.add_row(
            f"[green]● Optimal Orbit ({ok})[/green]",
            f"[yellow]● Lagging ({slow})[/yellow]",
            f"[red]✖ Broken Orbit ({fail})[/red]"
        )
        
        return Panel(
            Group(header, Text("- "*25, style="dim cyan"), orbital_view, Text("- "*25, style="dim cyan"), stats),
            title="[bold]Deep Space Telemetry[/bold]",
            border_style="cyan",
            padding=(1, 2)
        )

    def idle_cb(remaining, summary, history, wait_start):
        rotation[0] = (rotation[0] + 0.5) % 360 # Slow rotation in idle
        
        header = Text.assemble(
            ("● ", "green"), "SYSTEM STANDBY ", ("• ", "dim"), f"NEXT SYNC: {sim.format_duration(remaining)}"
        )
        
        orbital_view = get_orbital_map(summary.results, len(summary.results), rotation[0])
        
        status_msg = "[green]ORBITAL STABILITY VERIFIED[/green]" if summary.passed else "[red]⚠️  ORBITAL ANOMALIES DETECTED[/red]"
        stats = Table.grid(padding=(0, 3))
        stats.add_row(
            status_msg,
            f"Avg ping: {summary.avg_response_ms:.0f}ms"
        )
        
        return Panel(
            Group(header, Text("- "*25, style="dim"), orbital_view, Text("- "*25, style="dim"), stats),
            title="[bold]Deep Space Telemetry (Idle)[/bold]",
            border_style="dim green",
            padding=(1, 2)
        )

    await sim.run_app(
        timing,
        scanning_callback=scanning_cb,
        idle_callback=idle_cb,
        console=console,
        scan_fps=15,
        idle_fps=4
    )

if __name__ == "__main__":
    try:
        timing = sim.parse_args()
        asyncio.run(run_example(timing))
    except KeyboardInterrupt:
        sys.exit(0)
