from typing import Literal, Optional
from .state import State

Decision = Literal[
    "clarify_or_respond",
    "search_flights",
    "search_buses",
    "search_trains",
    "analyze_results",
    "end",
]

RouterAction = Literal[
    "clarify",
    "show_flights",
    "show_buses",
    "show_trains",
    "analyze_results",
]


def _infer_mode_from_countries(state: State) -> Optional[str]:
    origin_country = state.get("origin_country")
    destination_country = state.get("destination_country")
    if not origin_country or not destination_country:
        return None
    if origin_country.strip().lower() != destination_country.strip().lower():
        return "flight"
    return None


def _decide_action(state: State) -> RouterAction:
    origin = state.get("origin")
    destination = state.get("destination")
    date = state.get("date")
    mode = state.get("transport_mode")
    needs_refresh = state.get("needs_refresh", False)
    followup_request = state.get("followup_request")
    
    # Check if we have transport options available
    has_transport_options = bool(
        state.get("flight_options") 
        or state.get("bus_options") 
        or state.get("train_options")
    )
    
    # If we have transport options, parameters haven't changed (needs_refresh=False),
    # and there's a followup request, route to result analysis
    if has_transport_options and not needs_refresh and followup_request:
        return "analyze_results"

    if not origin or not destination or not date:
        return "clarify"

    if not needs_refresh:
        return "clarify"

    if not mode:
        inferred_mode = _infer_mode_from_countries(state)
        if inferred_mode == "flight":
            return "show_flights"
        return "clarify"

    if mode == "flight":
        return "show_flights"
    if mode == "bus":
        return "show_buses"
    if mode == "train":
        return "show_trains"

    return "clarify"


def router_node(state: State) -> dict:
    action = _decide_action(state)
    updates = {"next_action": action}
    if action == "show_flights" and not state.get("transport_mode"):
        inferred_mode = _infer_mode_from_countries(state)
        if inferred_mode:
            updates["transport_mode"] = inferred_mode
    return updates


def route_next(state: State) -> Decision:
    action = state.get("next_action") or _decide_action(state)

    if action == "show_flights":
        return "search_flights"
    if action == "show_buses":
        return "search_buses"
    if action == "show_trains":
        return "search_trains"
    if action == "analyze_results":
        return "analyze_results"

    return "clarify_or_respond"
