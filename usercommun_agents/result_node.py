from typing import Dict, List
import json
import os
import pprint

import google.generativeai as genai
from langchain_core.messages import AIMessage, HumanMessage, BaseMessage

from graph.state import State

# Debug flag - set to False to disable debug prints
DEBUG_MODE = False

genai.configure(api_key=os.environ.get("GOOGLE_API_KEY"))
_MODEL_NAME = os.getenv("GEMINI_MODEL_NAME", "gemini-2.0-flash")
_model = genai.GenerativeModel(_MODEL_NAME)


def _get_user_messages(messages: List[BaseMessage]) -> List[HumanMessage]:
    return [m for m in messages if isinstance(m, HumanMessage)]


def result_node(state: State) -> Dict:
    if DEBUG_MODE:
        print("\n=== DEBUG: Current State ===")
        # Convert state to dict to ensure we see all elements
        state_dict = dict(state) if hasattr(state, 'items') else state
        pprint.pprint(state_dict, width=120, sort_dicts=False, depth=None)
        print("=== End of State ===\n")
        
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
    mode = state.get("transport_mode")
    if not state.get("origin"):
        missing.append("origin city")
    if not state.get("destination"):
        missing.append("destination city")
    if not state.get("date"):
        missing.append("date")
    if not mode:
        missing.append("transport mode (flight/bus/train)")
    if missing:
        clarify_text = "I still need: " + ", ".join(missing)
    else:
        clarify_text = "I have all core fields; ready to show results once agents are implemented."

    flight_options = state.get("flight_options") or []
    bus_options = state.get("bus_options") or []
    train_options = state.get("train_options") or []
    
    # Check if we have any transport results
    has_results = bool(flight_options or bus_options or train_options)
    
    if missing:
        # Still missing required fields, just show clarification
        reply = f"{clarify_text}"
    elif has_results:
        # We have results, use LLM to format them nicely
        try:
            reply = _format_transport_results(
                state_view, flight_options, bus_options, train_options, mode
            )
        except Exception as e:
            # Fallback to basic formatting if LLM fails
            print(f"Error formatting results with LLM: {e}")
            reply = (
                f"I found {len(flight_options)} flight(s), {len(bus_options)} bus(es), "
                f"and {len(train_options)} train(s) available. "
                f"Here are the results:\n\n"
                f"{json.dumps({'flights': flight_options, 'buses': bus_options, 'trains': train_options}, ensure_ascii=False, indent=2)}"
            )
    else:
        # No results yet but all fields are complete
        reply = clarify_text

    return {"messages": [AIMessage(content=reply)]}


def _format_transport_results(
    state_view: Dict, flight_options: List, bus_options: List, train_options: List, transport_mode: str
) -> str:
    """Use LLM to format transport results with summaries and recommendations."""
    
    search_info = {
        "origin": state_view.get("origin", "Unknown"),
        "destination": state_view.get("destination", "Unknown"),
        "date": state_view.get("date", "Unknown"),
        "transport_mode": transport_mode or "any",
    }
    
    # Prepare the data for LLM analysis
    transport_data = {}
    if flight_options:
        transport_data["flights"] = flight_options
    if bus_options:
        transport_data["buses"] = bus_options
    if train_options:
        transport_data["trains"] = train_options
    prompt = (
        f"You are a helpful travel assistant presenting search results to a user.\n\n"
        f"Search Request:\n"
        f"- Origin: {search_info['origin']}\n"
        f"- Destination: {search_info['destination']}\n"
        f"- Date: {search_info['date']}\n"
        f"- Preferred transport mode: {search_info['transport_mode']}\n\n"
        f"Available Transport Options (JSON format):\n"
        f"{json.dumps(transport_data, ensure_ascii=False, indent=2)}\n\n"
        f"Please analyze these results and provide a clear recommendation focusing only on the available information.\n"
        f"1. Brief introduction with search details\n"
        f"2. Summary of available transport options\n"
        f"3. For each recommended option, include only the available information from these categories:\n"
        f"   - Departure and arrival stations\n"
        f"   - Transfer details (number of transfers, transfer points)\n"
        f"   - Distance and duration\n"
        f"   - Any other relevant journey details\n\n"
        f"Important guidelines:\n"
        f"- if a value is 0.0 try not to mention it \n"
        f"- Only mention information that is actually available in the data\n"
        f"- Do not mention or call out any missing information\n"
        f"- Keep the output clean and focused only on the available details\n"
        f"- Use simple, clear language without markdown formatting\n"
        f"- For multi-segment journeys, describe each segment with available details\n"
        f"- Return plain text only, no JSON or code blocks"
    )
    
    response = _model.generate_content(prompt)
    formatted_text = getattr(response, "text", "") or ""
    
    # Clean markdown code blocks if present
    formatted_text = formatted_text.strip()
    if formatted_text.startswith("```"):
        lines = formatted_text.splitlines()
        if len(lines) >= 2 and lines[0].startswith("```"):
            if lines[-1].startswith("```"):
                formatted_text = "\n".join(lines[1:-1]).strip()
    
    if not formatted_text:
        # Fallback if LLM returns empty
        formatted_text = ("LLM had no ouput"
        )
    
    return formatted_text
