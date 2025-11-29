from typing import Dict, List
import json
import os
import pprint

import google.generativeai as genai
from langchain_core.messages import AIMessage, HumanMessage, BaseMessage

from graph.state import State
from trans_agents.API_helper import simplify_flight_data

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
                f"(Error: {str(e)}) "
            )
    else:
        # No results found, but we have all required fields
        reply = (
            f"I searched for {mode} options from {state.get('origin')} to {state.get('destination')} "
            f"on {state.get('date')}, but unfortunately, I couldn't find any available results. "
            "Please try a different date, transport mode, or route."
        )

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
        # Simplify flight data to reduce token usage and avoid errors
        transport_data["flights"] = simplify_flight_data(flight_options)
    if bus_options:
        transport_data["buses"] = bus_options
    if train_options:
        transport_data["trains"] = train_options
    user_needs = state_view.get("needs", "None")

    prompt = (
        f"You are a highly professional and efficient travel agent assistant. Your goal is to present search results clearly, concisely, and helpfully.\n\n"
        f"Search Request:\n"
        f"- Origin: {search_info['origin']}\n"
        f"- Destination: {search_info['destination']}\n"
        f"- Date: {search_info['date']}\n"
        f"- Preferred transport mode: {search_info['transport_mode']}\n"
        f"- User Preferences/Needs: {user_needs}\n\n"
        
        f"FEW-SHOT EXAMPLES:\n"
        f"Example 1 (Specific Preference - Cheapest):\n"
        f"User Needs: 'cheapest flight'\n"
        f"Data: [Flight A ($100, 5h), Flight B ($200, 2h)]\n"
        f"Output:\n"
        f"I found the best option for you based on price:\n\n"
        f"- Best Match (Cheapest): Flight A is the most affordable at $100.\n"
        f"  - Departs: 10:00 AM | Arrives: 3:00 PM\n"
        f"  - Duration: 5h\n\n"
        f"If you prefer a faster trip, Flight B takes only 2h but costs $200.\n\n"
        
        f"Example 2 (General Search - Deduplication):\n"
        f"User Needs: 'None'\n"
        f"Data: [Flight A ($150, 2h) - Cheapest & Fastest, Flight B ($200, 3h)]\n"
        f"Output:\n"
        f"Here are the best options for your trip:\n\n"
        f"  -Top Pick (Cheapest & Fastest):Flight A is the clear winner at $150 and only 2h duration.\n"
        f"  - Departs: 08:00 AM | Arrives: 10:00 AM\n"
        f"  - Carrier: BA\n\n"
        f"  -Alternative: Flight B is available for $200 if the timing suits you better.\n"
        f"  - Departs: 12:00 PM | Arrives: 3:00 PM\n\n"

        f"Available Transport Options (JSON format):\n"
        f"{json.dumps(transport_data, ensure_ascii=False, indent=2)}\n\n"
        f"Please analyze these results and provide a clear recommendation.\n"
        f"CRITICAL INSTRUCTIONS:\n"
        f"1. Deduplication: If an option fits multiple categories (e.g., it is BOTH the cheapest and the fastest), mention it ONLY ONCE. Tag it with multiple attributes (e.g., 'Cheapest & Fastest'). DO NOT list the same option twice.\n"
        f"2. Sorting:\n"
        f"   - If the user has a preference (e.g., 'cheapest'), put that option FIRST.\n"
        f"   - If no preference, prioritize a balance of Price and Duration.\n"
        f"3. Structure:\n"
        f"   - Start with a polite, 1-sentence summary.\n"
        f"   - Use bullet points for options.\n"
        f"   - For each option, clearly state WHY you recommended it (e.g., 'Cheapest', 'Fastest', 'Balanced').\n"
        f"   - Include key details: Price, Duration, Departure/Arrival Times, Carrier/Agency.\n"
        f"4. Tone: Professional, concise, and helpful. Avoid robotic repetition.\n"
        f"5. Formatting:\n"
        f"   - Do NOT use markdown bold/italic (no  or *). Use plain text capitalization or labels like 'Option 1:' instead.\n"
        f"   - Use clean spacing.\n"
        f"   - Return PLAIN TEXT only.\n"
        f"6. Mixed Results Handling (CRITICAL):\n"
        f"   - Check the 'Preferred transport mode' in the Search Request.\n"
        f"   - Check the keys in 'Available Transport Options' (e.g., 'flights', 'buses', 'trains').\n"
        f"   - If the user asked for 'Train' but the JSON data ONLY contains 'buses' (or other non-train transport modes like Metro, Bus, etc.), you MUST start your response with: 'I couldn't find any train options for this route, but I found other transport options:'\n"
        f"   - DO NOT label a Bus option as a 'Train' option. If the data says 'bus', call it a Bus.\n"
        f"   - If the data contains mixed legs (e.g., Metro + Bus), describe it as a 'Multi-leg journey involving Metro and Bus', do NOT call it a 'Train' unless there is an actual train leg."
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
