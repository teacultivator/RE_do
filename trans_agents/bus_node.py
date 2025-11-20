from typing import Dict
from graph.state import State

def bus_node(state: State) -> Dict:
    return {
        "bus_options": state.get("bus_options") or [],
        "needs_refresh": False,
    }
