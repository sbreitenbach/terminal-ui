import asyncio
import sys
from rich.live import Live
from rich.panel import Panel
from rich.console import Console, Group
from rich.text import Text
from rich.tree import Tree

import scanner_sim as sim

def build_tree(results, total_expected, is_idle=False):
    """Builds a hierarchical tree view of the scanned endpoints."""
    # Basic data structure to hold the endpoint hierarchy
    tree_data = {}
    
    # Initialize tree with all known endpoints from sim
    for ep in sim.ENDPOINTS:
        parts = ep.strip("/").split("/")
        current_level = tree_data
        for i, part in enumerate(parts):
            if part not in current_level:
                current_level[part] = {"_status": None, "_time": None, "_children": {}}
            if i == len(parts) - 1:
                # We expect to fill this with scan results
                pass
            current_level = current_level[part]["_children"]
            
    # Overlay actual results
    for r in results:
        parts = r.endpoint.strip("/").split("/")
        current_level = tree_data
        for i, part in enumerate(parts):
            if i == len(parts) - 1:
                current_level[part]["_status"] = r.status
                current_level[part]["_time"] = r.response_time_ms
            current_level = current_level[part]["_children"]

    # Function to recursively build the Rich Tree
    def add_nodes(data_dict, rich_tree):
        for key, value in data_dict.items():
            node_label = Text(key, style="bold")
            
            # If it's a leaf node (an actual endpoint)
            if not value["_children"]:
                if value["_status"] is None:
                    # Not yet scanned
                    label = Text(f"○ {key}", style="dim")
                else:
                    # Scanned
                    icon = sim.status_emoji(value["_status"])
                    ms_color = "green" if value["_time"] < 200 else "yellow" if value["_time"] < 1000 else "red"
                    label = Text.assemble(
                        f"{icon} {key} ",
                        (f"[{value['_time']}ms]", ms_color)
                    )
                branch = rich_tree.add(label)
            else:
                # It's an intermediate directory/group
                # Determine color based on children's worst status
                branch_color = "blue"
                if any(v["_status"] == sim.EndpointStatus.ERROR for k,v in value["_children"].items()):
                     branch_color = "red"
                elif any(v["_status"] == sim.EndpointStatus.TIMEOUT for k,v in value["_children"].items()):
                     branch_color = "magenta"
                elif any(v["_status"] == sim.EndpointStatus.SLOW for k,v in value["_children"].items()):
                     branch_color = "yellow"
                
                label = Text(f"📁 {key}", style=f"bold {branch_color}")
                branch = rich_tree.add(label)
                add_nodes(value["_children"], branch)

    root_label = Text("🌐 API Gateway", style="bold cyan")
    main_tree = Tree(root_label, guide_style="bold bright_black")
    add_nodes(tree_data, main_tree)
    
    return main_tree


async def run_example(timing: sim.TimingConfig):
    console = Console()
    
    def scanning_cb(run_number, current, total, result, results, start_time, history):
        header = Text.assemble(
            ("🌳 ", "green"), "HIERARCHICAL MAP ", ("• ", "dim"), f"RUN #{run_number}",
            f"   | Progress: {current}/{total}"
        )
        
        tree_view = build_tree(results, total)
        
        return Panel(
            Group(header, Text(""), tree_view),
            title="[bold]API Topology[/bold]",
            border_style="green",
            padding=(1, 2)
        )

    def idle_cb(remaining, summary, history, wait_start):
        header = Text.assemble(
            ("● ", "green"), "TOPOLOGY IDLE ", ("• ", "dim"), f"NEXT SCAN: {sim.format_duration(remaining)}"
        )
        
        tree_view = build_tree(summary.results, len(summary.results), is_idle=True)
        
        return Panel(
            Group(header, Text(""), tree_view),
            title="[bold]API Topology (Idle)[/bold]",
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
