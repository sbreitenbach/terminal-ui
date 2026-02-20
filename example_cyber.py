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
    """Simulates a matrix-style falling characters background."""
    def __init__(self, width=70, height=10):
        self.width = width
        self.height = height
        self.cols = [random.randint(-20, 0) for _ in range(width)]

    def get_frame(self) -> Text:
        text = Text()
        for h in range(self.height):
            line = ""
            for w in range(min(self.width, 65)):
                if self.cols[w] == h:
                    line += "█"
                elif self.cols[w] > h and self.cols[w] < h + 5:
                    line += random.choice(".:*¤°")
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
    matrix = MatrixBackground()
    
    def scanning_cb(run_number, current, total, result, results, start_time, history):
        # Layout
        header = Align.center(CYBER_TITLE)
        
        # Active Status with pulsing
        pulse_color = "bold green" if int(sim.time.time() * 2) % 2 == 0 else "bold bright_green"
        status_box = Panel(
            Align.center(f"[{pulse_color}]SCANNING ACTIVE[/{pulse_color}]  |  Run #{run_number}  |  {current}/{total}"),
            border_style="green",
            padding=(0, 2)
        )

        # Progress "Bar" - Cyber style
        pct = int((current / total) * 30)
        bar = "█" * pct + "░" * (30 - pct)
        progress_text = Align.center(Text(f"LOAD: [{bar}] {int(current/total*100)}%", style="blue"))

        # Live Results with response times
        results_table = Table(box=None, expand=True, show_header=True, header_style="dim green")
        results_table.add_column("", width=2)
        results_table.add_column("METHOD", width=5)
        results_table.add_column("ENDPOINT")
        results_table.add_column("RESP", justify="right")
        results_table.add_column("CODE", justify="right")
        results_table.add_column("STATUS", justify="right")
        for r in results[-8:]:
            status_text = Text("OK", style="bold green") if r.status == sim.EndpointStatus.OK else Text(r.status.value.upper(), style="bold red")
            ms_style = "green" if r.response_time_ms < 200 else "yellow" if r.response_time_ms < 1000 else "red"
            results_table.add_row(
                Text(">>", style="dim green"),
                Text(r.method, style="dim cyan"),
                Text(r.endpoint, style="blue"),
                Text(f"{r.response_time_ms:>4d}ms", style=f"bold {ms_style}"),
                Text(str(r.status_code) if r.status_code else "---", style="dim"),
                status_text
            )
        
        results_panel = Panel(results_table, title="[green]DATALINK[/green]", border_style="dim green")

        # System status line at bottom
        ok_count = sum(1 for r in results if r.status == sim.EndpointStatus.OK)
        avg = sum(r.response_time_ms for r in results) / len(results) if results else 0
        elapsed = sim.time.time() - start_time
        sys_status = Align.center(Text.assemble(
            ("SYSTEMS: ", "dim green"),
            (f"{ok_count}/{len(results)} CLEAR", "bold green" if ok_count == len(results) else "bold yellow"),
            ("  |  AVG PING: ", "dim green"),
            (f"{avg:.0f}ms", "bold green" if avg < 200 else "bold yellow"),
            ("  |  UPTIME: ", "dim green"),
            (f"{sim.format_duration(elapsed)}", "green"),
        ))

        return Group(header, status_box, progress_text, results_panel, sys_status)

    def idle_cb(remaining, summary, history, wait_start):
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
            (f"{summary.avg_response_ms:.0f}ms avg", "bold black"),
            ("  STATUS: ", "dim green"),
            ("STABLE" if summary.passed else "BREACHED", "bold green" if summary.passed else "bold red"),
            ("  ENDPOINTS: ", "dim green"),
            (f"{len(summary.results)}", "green"),
        ))

        return Group(header, status_box, bg, summary_text)

    await sim.run_app(
        timing,
        scanning_callback=scanning_cb,
        idle_callback=idle_cb,
        scan_fps=10,
        idle_fps=10
    )

if __name__ == "__main__":
    try:
        timing = sim.parse_args()
        asyncio.run(run_example(timing))
    except KeyboardInterrupt:
        sys.exit(0)
