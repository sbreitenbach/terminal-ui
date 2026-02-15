import asyncio
import sys
import random
from rich.console import Group
from rich.live import Live
from rich.panel import Panel
from rich.table import Table
from rich.text import Text
from rich.align import Align
from rich.style import Style

import scanner_sim as sim

# --- ASCII Art Header ---
CYBER_TITLE = """
[bold green]▄▀▄ █▀█ █   █▀ █▀▀ ▄▀▄ █▄ █[/bold green]
[bold green]█▀█ █▀▀ █   ▄█ █   █▀█ █ ▀█ [dim]v1.0[/dim][/bold green]
"""

class MatrixBackground:
    """Simulates a matrix-style falling characters or dots background."""
    def __init__(self, width=60, height=8):
        self.width = width
        self.height = height
        self.cols = [random.randint(-20, 0) for _ in range(width)]

    def get_frame(self) -> Text:
        text = Text()
        for h in range(self.height):
            line = ""
            for w in range(min(self.width, 50)): # limit width
                if self.cols[w] == h:
                    line += "█"
                elif self.cols[w] > h and self.cols[w] < h + 5:
                    line += random.choice(".:*")
                else:
                    line += " "
            text.append(line + "\n", style="green")
            
        # Update cols
        for i in range(len(self.cols)):
            self.cols[i] += 1
            if self.cols[i] > self.height + 10:
                self.cols[i] = random.randint(-10, 0)
        return text

async def run_example(timing: sim.TimingConfig):
    run_number = 1
    matrix = MatrixBackground()
    
    while True:
        # --- Scanning State ---
        results = []
        start_time = sim.time.time()
        
        with Live(refresh_per_second=10) as live:
            async for current, total, result in sim.simulate_scan(timing, run_number):
                results.append(result)
                
                # Layout
                header = Align.center(CYBER_TITLE)
                
                # Active Status
                pulse_color = "bold green" if int(sim.time.time() * 2) % 2 == 0 else "bold bright_green"
                status_box = Panel(
                    Align.center(f"[{pulse_color}]SCANNING ACTIVE[/{pulse_color}]  |  Run #{run_number}"),
                    border_style="green",
                    padding=(0, 2)
                )

                # Progress "Bar" - Cyber style
                pct = int((current / total) * 20)
                bar = "█" * pct + " " * (20 - pct)
                progress_text = Align.center(Text(f"LOAD: [{bar}] {int(current/total*100)}%", style="cyan"))

                # Live Results
                results_table = Table(box=None, expand=True, show_header=False)
                for r in results[-6:]:
                    status_text = Text("OK", style="bold green") if r.status == sim.EndpointStatus.OK else Text(r.status.value.upper(), style="bold red")
                    results_table.add_row(
                        Text(">>", style="dim green"),
                        Text(r.endpoint, style="cyan"),
                        Text(f"{r.response_time_ms:03d}ms", style="bold white"),
                        status_text
                    )
                
                results_panel = Panel(results_table, title="[green]DATALINK[/green]", border_style="dim green")

                live.update(Group(header, status_box, progress_text, results_panel))

        # Scan complete
        summary = sim.ScanSummary(run_number, results, start_time, sim.time.time())
        sim.notify_scan_complete(summary)
        
        # --- Waiting State ---
        wait_start = sim.time.time()
        while sim.time.time() - wait_start < timing.wait_duration_seconds:
            remaining = timing.wait_duration_seconds - (sim.time.time() - wait_start)
            
            header = Align.center(CYBER_TITLE)
            
            # Idle Status
            status_box = Panel(
                Align.center(f"[dim green]SYSTEM IDLE[/dim green]  |  Next pulse: {sim.format_duration(remaining)}"),
                border_style="dim green",
                padding=(0, 2)
            )

            # Ambient Matrix animation
            bg = matrix.get_frame()
            
            # Last Results Summary
            summary_text = Align.center(Text.assemble(
                ("LAST SCAN: ", "dim green"),
                (f"{summary.avg_response_ms:.0f}ms", "bold white"),
                ("  STATUS: ", "dim green"),
                ("STABLE" if summary.passed else "BREACHED", "bold green" if summary.passed else "bold red")
            ))

            with Live(refresh_per_second=10) as live:
                live.update(Group(header, status_box, bg, summary_text))
                await asyncio.sleep(0.1)
                if sim.time.time() - wait_start >= timing.wait_duration_seconds:
                    break
        
        run_number += 1

if __name__ == "__main__":
    try:
        timing = sim.parse_args()
        asyncio.run(run_example(timing))
    except KeyboardInterrupt:
        sys.exit(0)
