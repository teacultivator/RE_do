from typing import Literal

from .state import State


Decision = Literal[
    "clarify_or_respond",
    "search_flights",
    "search_buses",
    "search_trains",
    "end",
]

RouterAction = Literal[
    "clarify",
    "show_flights",
    "show_buses",
    "show_trains",
]


def _decide_action(state: State) -> RouterAction:
    origin = state.get("origin")
    destination = state.get("destination")
    date = state.get("date")
    mode = state.get("transport_mode")

    if not origin or not destination or not date:
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
    return {"next_action": action}


def route_next(state: State) -> Decision:
    action = state.get("next_action") or _decide_action(state)

    if action == "show_flights":
        return "search_flights"
    if action == "show_buses":
        return "search_buses"
    if action == "show_trains":
        return "search_trains"

    return "clarify_or_respond"
