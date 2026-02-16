import asyncio
import sys
from rich.live import Live
from rich.panel import Panel
from rich.table import Table
from rich.console import Console, Group
from rich.text import Text
from rich.box import DOUBLE, ROUNDED

import scanner_sim as sim

def hud_status(result):
    color = "green" if result.status == sim.EndpointStatus.OK else "yellow" if result.status == sim.EndpointStatus.SLOW else "red"
    ms_style = "green" if result.response_time_ms < 200 else "yellow" if result.response_time_ms < 1000 else "red"
    return Text.assemble(
        ("[ ", "dim"), (sim.status_emoji(result.status), color), (" ] ", "dim"),
        (result.method, "dim cyan"), (" ", ""),
        (result.endpoint, "bold"),
        (" -> ", "dim"), (f"{result.response_time_ms}ms", ms_style),
        (" ", ""), (f"[{result.status_code or '---'}]", "dim"),
    )

async def run_example(timing: sim.TimingConfig):
    console = Console()
    run_number = 1
    
    while True:
        results = []
        start_time = sim.time.time()
        
        with Live(refresh_per_second=10) as live:
            async for current, total, result in sim.simulate_scan(timing, run_number):
                results.append(result)
                
                pct = int(current / total * 100)
                header = Text.assemble(
                    (">>> ", "cyan"), "TACTICAL SCANNER ", ("v4.0", "dim"),
                    f" | RUN_{run_number} | TARGETS: {current}/{total} ({pct}%)"
                )
                
                # Active view: show targeting brackets around current
                main_display = Table.grid(expand=True)
                for r in results[-10:]:  # Show last 10
                    main_display.add_row(hud_status(r))
                
                if current < total:
                    main_display.add_row(Text.assemble(
                        ("[ ", "cyan"), ("TARGETING...", "blink cyan"), (" ]", "cyan")
                    ))

                # Stats with counts
                ok = sum(1 for r in results if r.status == sim.EndpointStatus.OK)
                fail = sum(1 for r in results if r.status in [sim.EndpointStatus.ERROR, sim.EndpointStatus.TIMEOUT])
                slow = sum(1 for r in results if r.status == sim.EndpointStatus.SLOW)
                avg = sum(r.response_time_ms for r in results) / len(results) if results else 0
                
                stats = Table.grid(padding=(0, 2))
                stats.add_row(
                    f"OK: [green]{ok}[/green]",
                    f"WARN: [yellow]{slow}[/yellow]",
                    f"FAIL: [red]{fail}[/red]",
                    f"AVG: [cyan]{avg:.0f}ms[/cyan]"
                )

                # Mission status
                mission_color = "green" if fail == 0 else "red"
                mission_text = Text.assemble(
                    ("  MISSION STATUS: ", "dim cyan"),
                    ("ALL CLEAR" if fail == 0 else f"⚠ {fail} TARGET(S) HOSTILE", f"bold {mission_color}"),
                )

                live.update(Panel(
                    Group(header, Text("─" * 50, style="dim cyan"), main_display, Text("─" * 50, style="dim cyan"), stats, mission_text),
                    title="[bold cyan]HUD CONSOLE[/bold cyan]",
                    border_style="cyan",
                    box=DOUBLE,
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
                (">>> ", "green"), "SYSTEM STANDBY ", ("v4.0", "dim"),
                f" | NEXT_ENGAGEMENT: {sim.format_duration(remaining)}"
            )
            
            main_display = Table.grid(expand=True)
            main_display.add_row(Text("SCAN ARCHIVE LOADED...", style="dim"))
            for r in results[:6]:
                 main_display.add_row(hud_status(r))
            main_display.add_row(Text(f"... +{len(results) - 6} more", style="dim"))

            # Idle mission status
            mission_color = "green" if summary.passed else "yellow"
            mission_text = Text.assemble(
                ("  LAST MISSION: ", "dim"),
                ("COMPLETE" if summary.passed else "PARTIAL", f"bold {mission_color}"),
                (f"  |  {summary.avg_response_ms:.0f}ms avg  |  {sim.format_time(summary.end_time)}", "dim"),
            )

            with Live(refresh_per_second=4) as live:
                style = "green" if summary.passed else "yellow"
                live.update(Panel(
                    Group(header, Text("─" * 50, style="dim"), main_display, Text("─" * 50, style="dim"), mission_text),
                    title=f"[bold {style}]HUD CONSOLE (IDLE)[/bold {style}]",
                    border_style=style,
                    box=DOUBLE,
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
