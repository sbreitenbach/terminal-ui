import asyncio
import sys
import math
from rich.live import Live
from rich.panel import Panel
from rich.table import Table
from rich.console import Console, Group
from rich.text import Text

import scanner_sim as sim

# Helix constants
HELIX_HEIGHT = 20
HELIX_WIDTH = 40
CENTER_X = 20
AMPLITUDE = 8  # Radius of helix

def get_helix_visualization(results, total_expected, rotation_angle, scanning=True):
    """Create a rotating DNA helix visualization."""
    canvas = [[" " for _ in range(HELIX_WIDTH)] for _ in range(HELIX_HEIGHT)]
    
    # Calculate positions for both strands
    strand1_positions = []
    strand2_positions = []
    
    for i in range(total_expected):
        # Vertical position
        y = int((i / total_expected) * (HELIX_HEIGHT - 1))
        
        # Helical angle
        base_angle = (i / total_expected) * 4 * math.pi  # 2 full rotations
        angle1 = base_angle + math.radians(rotation_angle)
        angle2 = angle1 + math.pi  # Opposite strand
        
        # X positions
        x1 = int(CENTER_X + AMPLITUDE * math.cos(angle1))
        x2 = int(CENTER_X + AMPLITUDE * math.cos(angle2))
        
        # Determine which strand is "in front" (closer to viewer)
        z1 = math.sin(angle1)
        z2 = math.sin(angle2)
        
        strand1_positions.append((x1, y, z1, i))
        strand2_positions.append((x2, y, z2, i))
    
    # Draw horizontal connecting bars between strand pairs at same y
    for i in range(total_expected):
        x1, y1, z1, _ = strand1_positions[i]
        x2, y2, z2, _ = strand2_positions[i]
        if y1 == y2 and 0 <= y1 < HELIX_HEIGHT:
            lo = min(x1, x2) + 1
            hi = max(x1, x2)
            for x in range(lo, hi):
                if 0 <= x < HELIX_WIDTH and canvas[y1][x] == " ":
                    canvas[y1][x] = ("[dim]─[/dim]", "dim")
    
    # Sort by z-depth (back to front) for proper layering
    all_positions = strand1_positions + strand2_positions
    all_positions.sort(key=lambda p: p[2])
    
    # Draw connection lines (backbone)
    for i in range(len(all_positions) - 1):
        x1, y1, z1, idx1 = all_positions[i]
        x2, y2, z2, idx2 = all_positions[i + 1]
        
        # Only connect points that are close vertically
        if abs(y1 - y2) <= 1 and 0 <= y1 < HELIX_HEIGHT and 0 <= x1 < HELIX_WIDTH:
            if z1 < 0:  # Behind
                if canvas[y1][x1] == " ":
                    canvas[y1][x1] = ("[dim]·[/dim]", "dim")
    
    # Draw nodes on top of lines
    for strand_idx, positions in enumerate([strand1_positions, strand2_positions]):
        strand_color = "cyan" if strand_idx == 0 else "magenta"
        
        for x, y, z, i in positions:
            if 0 <= y < HELIX_HEIGHT and 0 <= x < HELIX_WIDTH:
                if i < len(results):
                    r = results[i]
                    status_color = {
                        sim.EndpointStatus.OK: "green",
                        sim.EndpointStatus.SLOW: "yellow",
                        sim.EndpointStatus.TIMEOUT: "red",
                        sim.EndpointStatus.ERROR: "magenta",
                    }.get(r.status, "white")
                    
                    # Node character based on depth
                    if z > 0:  # In front
                        char = "●"
                        canvas[y][x] = (f"[bold {status_color}]{char}[/bold {status_color}]", status_color)
                    else:  # Behind
                        char = "○"
                        canvas[y][x] = (f"[{status_color}]{char}[/{status_color}]", status_color)
                else:
                    # Pending endpoint
                    char = "○" if z > 0 else "·"
                    canvas[y][x] = (f"[dim]{char}[/dim]", "dim")
                
                # Add endpoint label to the right of rightmost node
                if i < len(results):
                    r = results[i]
                    label = r.endpoint.split('/')[-1][:5]
                    label_start = max(x1, x2) + 2 if strand_idx == 0 else max(x1, x2) + 2
                    # Only place label if it fits on the canvas row
                    if 0 <= y < HELIX_HEIGHT and label_start + len(label) < HELIX_WIDTH:
                        placed = True
                        for c_idx, ch in enumerate(label):
                            cx = label_start + c_idx
                            if canvas[y][cx] != " ":
                                placed = False
                                break
                        if placed:
                            for c_idx, ch in enumerate(label):
                                cx = label_start + c_idx
                                canvas[y][cx] = (f"[dim]{ch}[/dim]", "dim")
    
    # Convert canvas to text
    lines = []
    for row in canvas:
        line = Text()
        for cell in row:
            if isinstance(cell, tuple):
                line.append_text(Text.from_markup(cell[0]))
            else:
                line.append(cell)
        lines.append(line)
    
    return Group(*lines)

async def run_example(timing: sim.TimingConfig):
    console = Console()
    rotation = [0]
    
    def scanning_cb(run_number, current, total, result, results, start_time, history):
        rotation[0] = (rotation[0] + 8) % 360
        
        header = Text.assemble(
            ("🧬 ", "blue"), "HELIX SCANNER ", ("• ", "dim"), f"RUN #{run_number}",
            f" | {current}/{total} SEQUENCED",
            ("  OK:", "dim"), (f"{sum(1 for r in results if r.status == sim.EndpointStatus.OK)}", "green"),
            ("  ERR:", "dim"), (f"{sum(1 for r in results if r.status in [sim.EndpointStatus.ERROR, sim.EndpointStatus.TIMEOUT])}", "red"),
        )
        
        helix = get_helix_visualization(results, total, rotation[0], scanning=True)
        
        # Stats
        stats = Table.grid(padding=(0, 2))
        stats.add_row(
            f"[green]OK: {sum(1 for r in results if r.status == sim.EndpointStatus.OK)}[/green]",
            f"[yellow]SLOW: {sum(1 for r in results if r.status == sim.EndpointStatus.SLOW)}[/yellow]",
            f"[red]ERROR: {sum(1 for r in results if r.status in [sim.EndpointStatus.ERROR, sim.EndpointStatus.TIMEOUT])}[/red]"
        )
        
        return Panel(
            Group(header, helix, stats),
            title="[bold]DNA Sequence Analyzer[/bold]",
            border_style="blue",
            padding=(1, 1)
        )

    def idle_cb(remaining, summary, history, wait_start):
        rotation[0] = (rotation[0] + 2) % 360
        
        header = Text.assemble(
            ("● ", "green"), "SEQUENCE STABLE ", ("• ", "dim"), f"NEXT SCAN: {sim.format_duration(remaining)}"
        )
        
        helix = get_helix_visualization(summary.results, len(summary.results), rotation[0], scanning=False)
        
        # Summary info
        info = Table.grid(padding=(0, 2))
        status_text = "[green]SEQUENCE COMPLETE[/green]" if summary.passed else "[red]⚠️  ANOMALIES DETECTED[/red]"
        info.add_row(
            status_text,
            f"Nodes: {len(summary.results)}",
            f"Avg: {summary.avg_response_ms:.0f}ms"
        )
        
        return Panel(
            Group(header, helix, info),
            title="[bold]DNA Sequence Analyzer (Idle)[/bold]",
            border_style="dim green",
            padding=(1, 1)
        )

    await sim.run_app(
        timing,
        scanning_callback=scanning_cb,
        idle_callback=idle_cb,
        console=console,
        scan_fps=15,
        idle_fps=10
    )

if __name__ == "__main__":
    try:
        timing = sim.parse_args()
        asyncio.run(run_example(timing))
    except KeyboardInterrupt:
        sys.exit(0)
