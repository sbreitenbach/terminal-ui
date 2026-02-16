import asyncio
import sys
import math
from rich.live import Live
from rich.panel import Panel
from rich.console import Console, Group
from rich.text import Text

import scanner_sim as sim

# Radar constants
RADIUS = 10
CENTER = (12, 12)
WIDTH = 25
HEIGHT = 20

def get_radar_sweep(angle_deg, results, total_expected):
    """Draws a radar sweep on a virtual canvas as a string with Rich markup."""
    rows = []
    angle_rad = math.radians(angle_deg)
    
    # Pre-calculate endpoint positions
    endpoint_pos = []
    for i in range(total_expected):
        a = (i / total_expected) * 360
        ar = math.radians(a)
        x = int(CENTER[0] + (RADIUS - 2) * math.cos(ar))
        y = int(CENTER[1] + (RADIUS - 2) * math.sin(ar) / 2) # Squish for terminal aspect ratio
        endpoint_pos.append((x, y))

    for y in range(HEIGHT):
        row_text = ""
        for x in range(WIDTH):
            dx = x - CENTER[0]
            dy = (y - CENTER[1]) * 2 # Correct aspect ratio
            dist = math.sqrt(dx*dx + dy*dy)
            
            # Draw circle bounds
            if abs(dist - RADIUS) < 0.5:
                row_text += "[dim white]·[/dim white]"
                continue
            
            # Draw center
            if x == CENTER[0] and y == CENTER[1]:
                row_text += "[blue]×[/blue]"
                continue

            # Draw endpoints
            is_endpoint = False
            for i, (ex, ey) in enumerate(endpoint_pos):
                if x == ex and y == ey:
                    if i < len(results):
                        r = results[i]
                        color = "green" if r.status == sim.EndpointStatus.OK else "red"
                        row_text += f"[{color}]■[/{color}]"
                    else:
                        row_text += "[dim]○[/dim]"
                    is_endpoint = True
                    break
            if is_endpoint: continue

            # Draw sweep line
            p_angle = math.degrees(math.atan2(dy, dx)) % 360
            diff = (angle_deg - p_angle + 360) % 360
            if dist < RADIUS and diff < 30:
                opacity = 1.0 - (diff / 30.0)
                if opacity > 0.8: char = "█"
                elif opacity > 0.5: char = "▓"
                else: char = "▒"
                row_text += f"[blue]{char}[/blue]"
            else:
                row_text += " "
        rows.append(row_text)
    
    return "\n".join(rows)

async def run_example(timing: sim.TimingConfig):
    console = Console()
    run_number = 1
    angle = 0
    
    with Live(refresh_per_second=15) as live:
        while True:
            results = []
            start_time = sim.time.time()
            
            async for current, total, result in sim.simulate_scan(timing, run_number):
                results.append(result)
                
                # Animate for a few frames while waiting for next result
                for _ in range(5):
                    angle = (angle + 12) % 360
                    header = Text.assemble(
                        ("⌖ ", "blue"), "RADAR SCANNING ", ("• ", "dim"), f"RUN #{run_number}",
                        f" | {current}/{total} PINGED"
                    )
                    radar_view = get_radar_sweep(angle, results, total)
                    live.update(Panel(
                        Group(header, Text.from_markup(radar_view)),
                        title="[bold]Deep Space Sonar[/bold]",
                        border_style="blue",
                        padding=(1, 2)
                    ))
                    await asyncio.sleep(0.05)
            
            summary = sim.ScanSummary(run_number, results, start_time, sim.time.time())
            sim.notify_scan_complete(summary)
            run_number += 1
            
            # Idle State
            wait_start = sim.time.time()
            while sim.time.time() - wait_start < timing.wait_duration_seconds:
                remaining = timing.wait_duration_seconds - (sim.time.time() - wait_start)
                angle = (angle + 3) % 360
                
                header = Text.assemble(
                    ("● ", "green"), "RADAR STANDBY ", ("• ", "dim"), f"NEXT SWEEP: {sim.format_duration(remaining)}"
                )
                radar_view = get_radar_sweep(angle, results, len(results))
                
                live.update(Panel(
                    Group(header, Text.from_markup(radar_view)),
                    title="[bold]Deep Space Sonar (Idle)[/bold]",
                    border_style="dim green",
                    padding=(1, 2)
                ))
                await asyncio.sleep(0.1)
                if sim.time.time() - wait_start >= timing.wait_duration_seconds:
                    break

if __name__ == "__main__":
    try:
        timing = sim.parse_args()
        asyncio.run(run_example(timing))
    except KeyboardInterrupt:
        sys.exit(0)
