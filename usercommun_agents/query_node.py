import json
import os
from datetime import datetime
from typing import Any, Dict, List, Optional

import google.generativeai as genai
from langchain_core.messages import BaseMessage, HumanMessage

from graph.state import State

genai.configure(api_key=os.environ["GOOGLE_API_KEY"])
_MODEL_NAME = os.getenv("GEMINI_MODEL_NAME", "gemini-2.0-flash")
_model = genai.GenerativeModel(_MODEL_NAME)

_REQUIRED_FIELDS = ("origin", "destination", "date", "transport_mode")

def _get_last_human(messages: List[BaseMessage]) -> Optional[str]:
    for m in reversed(messages):
        if isinstance(m, HumanMessage):
            return m.content
    return None


def _is_state_complete(state: State) -> bool:
    return all(state.get(field) for field in _REQUIRED_FIELDS)


def _missing_required_fields(state: State) -> List[str]:
    return [field for field in _REQUIRED_FIELDS if not state.get(field)]


def _looks_like_followup(message: str, state_complete: bool, state: State) -> bool:
    """
    Use LLM to determine if the message is a followup request about existing results
    rather than a request to change search parameters.
    """
    if not state_complete or not message:
        return False
    
    # Check if we have any transport options available
    has_options = bool(
        state.get("flight_options") 
        or state.get("bus_options") 
        or state.get("train_options")
    )
    
    if not has_options:
        return False
    
    # Use LLM to determine if this is a followup about existing results
    prompt = (
        "Determine if the user's message is asking about or analyzing existing travel results "
        "(like asking for details, filtering, sorting, comparing options, or getting more info), "
        "OR if they are trying to change the search parameters (origin, destination, date, transport mode).\n\n"
        "Current search parameters:\n"
        f"  Origin: {state.get('origin', 'not set')}\n"
        f"  Destination: {state.get('destination', 'not set')}\n"
        f"  Date: {state.get('date', 'not set')}\n"
        f"  Transport mode: {state.get('transport_mode', 'not set')}\n\n"
        f"User message: {json.dumps(message)}\n\n"
        "Respond with a JSON object with a single boolean field 'is_followup':\n"
        "- true if the user is asking about/examining existing results (details, filters, comparisons, etc.)\n"
        "- false if they are trying to change search parameters or make a new search\n"
        "Return only the JSON object, no extra text."
    )
    
    try:
        response = _call_gemini(prompt)
        return response.get("is_followup", False)
    except Exception as e:
        # Fallback: if LLM fails, default to False (treat as parameter change)
        print(f"Error in followup detection: {e}, defaulting to False")
        return False

def _clean_json_text(text: str) -> str:
    text = text.strip()
    if text.startswith("```"):
        lines = text.splitlines()
        if len(lines) >= 2 and lines[0].startswith("```"):
            if lines[-1].startswith("```"):
                return "\n".join(lines[1:-1]).strip()
    return text

def _call_gemini(prompt: str) -> Dict[str, Any]:
    response = _model.generate_content(prompt)
    raw = getattr(response, "text", "") or ""
    cleaned = _clean_json_text(raw)
    data = json.loads(cleaned)
    if not isinstance(data, dict):
        raise ValueError("Model did not return a JSON object")
    return data

def query_node(state: State) -> Dict[str, Any]:
    messages = list(state.get("messages", []))
    last_user = _get_last_human(messages)
    if last_user is None:
        return {}

    updates: Dict[str, Any] = {}
    state_complete = _is_state_complete(state)
    treat_as_followup = False

    should_call_llm = not _looks_like_followup(last_user, state_complete, state)

    snapshot: Dict[str, Any] = {
        "origin": state.get("origin"),
        "destination": state.get("destination"),
        "date": state.get("date"),
        "time": state.get("time"),
        "transport_mode": state.get("transport_mode"),
        "origin_country": state.get("origin_country"),
        "destination_country": state.get("destination_country"),
    }

    if should_call_llm:
        now_iso = datetime.now().isoformat()

        prompt = (
            "You convert a user's natural language travel request into a JSON patch for the current state.\n"
            "Current system datetime (ISO): "
            + now_iso
            + "\nCurrent state (may contain nulls): "
            + json.dumps(snapshot)
            + "\nUser message: "
            + json.dumps(last_user)
            + "\nRespond with a JSON object containing only the keys you want to update. "
            "Allowed keys: origin, destination, date, time, transport_mode, origin_country, destination_country, needs. "
            "Try to almost always infer origin_country and destination_country whenever the cities imply them and have a value for country fields for both (e.g., 'Paris' implies France). "
            "If the new message does not clearly change a field, do not include that key. "
            "Resolve relative dates like 'tomorrow' or 'next Monday' into concrete ISO dates (YYYY-MM-DD) using the current datetime. "
            "If the user says 'ASAP', 'immediately', or 'now', use the current date (today). "
            "Return only the JSON object, no extra text."
        )

        patch = _call_gemini(prompt)
        allowed_keys = {
            "origin",
            "destination",
            "date",
            "time",
            "transport_mode",
            "origin_country",
            "destination_country",
            "needs",
        }
        changes: Dict[str, Any] = {}
        for key in allowed_keys:
            if key in patch:
                value = patch[key]
                if value != state.get(key):
                    changes[key] = value

        if changes:
            # --- VALIDATION LOGIC START ---
            
            # 1. Validate Date (Reject Past Dates)
            if "date" in changes and changes["date"]:
                try:
                    input_date_str = changes["date"]
                    input_date = datetime.strptime(input_date_str, "%Y-%m-%d").date()
                    current_date = datetime.now().date()
                    
                    if input_date < current_date:
                        # Reject past date
                        print(f"Validation Error: Date {input_date_str} is in the past.")
                        # We can either clear it or not update it. Let's not update it.
                        if "date" in changes:
                            del changes["date"]
                        # Optionally, we could add a system message to warn the user, 
                        # but for now, ignoring the update will force the system to ask again 
                        # or keep the old valid date.
                except ValueError:
                    # Date format error, ignore or handle gracefully
                    pass

            # 2. Validate Origin == Destination
            # We need to check the prospective state (current state + changes)
            prospective_origin = changes.get("origin") or snapshot.get("origin")
            prospective_dest = changes.get("destination") or snapshot.get("destination")
            
            if prospective_origin and prospective_dest:
                if prospective_origin.lower().strip() == prospective_dest.lower().strip():
                    print(f"Validation Error: Origin and Destination are the same ({prospective_origin}).")
                    # Clear the destination in the updates to force a re-ask
                    changes["destination"] = None
                    # Also ensure we don't keep the old destination if it was the same
                    if "destination" not in changes:
                        changes["destination"] = None
            
            # --- VALIDATION LOGIC END ---

            updates.update(changes)
            prospective_state = dict(snapshot)
            # Apply changes again after validation modifications
            prospective_state.update(changes)
            
            missing_after_update = _missing_required_fields(prospective_state)
            missing_only_mode = len(missing_after_update) == 1 and missing_after_update[0] == "transport_mode"
            updates["needs_refresh"] = _is_state_complete(prospective_state) or missing_only_mode
            updates["followup_request"] = None
        else:
            treat_as_followup = state_complete
    else:
        treat_as_followup = state_complete

    if treat_as_followup:
        updates["needs_refresh"] = False
        updates["followup_request"] = last_user

    if "needs_refresh" not in updates:
        current_missing = _missing_required_fields(state)
        updates["needs_refresh"] = len(current_missing) == 1 and current_missing[0] == "transport_mode"
    if "followup_request" not in updates:
        updates["followup_request"] = None

    return updates
