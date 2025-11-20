from tkinter import N
from typing import Dict, List
import json

from langchain_core.messages import AIMessage, HumanMessage, BaseMessage

from graph.state import State


def _get_user_messages(messages: List[BaseMessage]) -> List[HumanMessage]:
    return [m for m in messages if isinstance(m, HumanMessage)]


def result_node(state: State) -> Dict:
    messages: List[BaseMessage] = list(state.get("messages", []))
    user_messages = _get_user_messages(messages)
    turn = len(user_messages)

    if user_messages:
        last_user = user_messages[-1].content
    else:
        last_user = "nothing yet"

    if len(user_messages) >= 2:
        prev_user = user_messages[-2].content
        prev_part = f"Previously you said: {prev_user}"
    else:
        prev_part = "No previous user message."

    state_view = {
        "origin": state.get("origin"),
        "destination": state.get("destination"),
        "date": state.get("date"),
        "time": state.get("time"),
        "transport_mode": state.get("transport_mode"),
        "origin_country": state.get("origin_country"),
        "destination_country": state.get("destination_country"),
        "needs": state.get("needs"),
        "next_action": state.get("next_action"),
    }

    missing = []
    if not state.get("origin"):
        missing.append("origin city")
    if not state.get("destination"):
        missing.append("destination city")
    if not state.get("date"):
        missing.append("date")
    if not state.get("transport_mode"):
        missing.append("transport mode (flight/bus/train)")
    elif state.get("transport_mode") == "bus" or "train":
        if not state.get("time"):
            missing.append("time")
    if missing:
        clarify_text = "I still need: " + ", ".join(missing)
    else:
        clarify_text = "I have all core fields; ready to show results once agents are implemented."

    transport_view = {
        "flights": state.get("flight_options") or [],
        "buses": state.get("bus_options") or [],
        "trains": state.get("train_options") or [],
    }

    reply = (
        f"This is turn {turn}. You just said: {last_user}. {prev_part}\n"
        f"Router next_action={state.get('next_action')!r}. {clarify_text}\n"
        f"Transport results (as collected so far): {json.dumps(transport_view, ensure_ascii=False)}\n"
        f"Parsed state: {json.dumps(state_view, ensure_ascii=False)}"
    )

    return {"messages": [AIMessage(content=reply)]}
