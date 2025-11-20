from typing import Literal

from langgraph.checkpoint.memory import MemorySaver
from langgraph.graph import END, StateGraph

from .state import State
from usercommun_agents.query_node import query_node
from usercommun_agents.result_node import result_node
from trans_agents.bus_node import bus_node
from trans_agents.train_node import train_node
from trans_agents.flight_node import flight_node


Decision = Literal[
    "clarify_or_respond",
    "search_flights",
    "search_buses",
    "search_trains",
    "end",
]


def router_node(state: State) -> dict:
    return {}


def route_next(state: State) -> Decision:
    origin = state.get("origin")
    destination = state.get("destination")
    date = state.get("date")

    if not origin or not destination or not date:
        return "clarify_or_respond"

    mode = state.get("transport_mode")
    if mode == "flight":
        return "search_flights"
    if mode == "bus":
        return "search_buses"
    if mode == "train":
        return "search_trains"

    return "clarify_or_respond"


def build_graph():
    builder = StateGraph(State)

    builder.add_node("query", query_node)
    builder.add_node("router", router_node)
    builder.add_node("flight", flight_node)
    builder.add_node("bus", bus_node)
    builder.add_node("train", train_node)
    builder.add_node("result", result_node)

    builder.set_entry_point("query")
    builder.add_edge("query", "router")

    builder.add_conditional_edges(
        "router",
        route_next,
        {
            "clarify_or_respond": "result",
            "search_flights": "flight",
            "search_buses": "bus",
            "search_trains": "train",
            "end": END,
        },
    )

    builder.add_edge("flight", "result")
    builder.add_edge("bus", "result")
    builder.add_edge("train", "result")

    checkpointer = MemorySaver()

    return builder.compile(checkpointer=checkpointer)


