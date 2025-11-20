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
_FOLLOWUP_KEYWORDS = (
    "detail",
    "details",
    "more info",
    "more about",
    "option",
    "options",
    "show",
    "filter",
    "sort",
    "cheapest",
    "fastest",
    "shortest",
    "compare",
    "list",
)

def _get_last_human(messages: List[BaseMessage]) -> Optional[str]:
    for m in reversed(messages):
        if isinstance(m, HumanMessage):
            return m.content
    return None


def _is_state_complete(state: State) -> bool:
    return all(state.get(field) for field in _REQUIRED_FIELDS)


def _missing_required_fields(state: State) -> List[str]:
    return [field for field in _REQUIRED_FIELDS if not state.get(field)]


def _looks_like_followup(message: str, state_complete: bool) -> bool:
    if not state_complete or not message:
        return False
    lower = message.lower()
    return any(keyword in lower for keyword in _FOLLOWUP_KEYWORDS)

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

    should_call_llm = not _looks_like_followup(last_user, state_complete)

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
            "Infer origin_country and destination_country whenever the cities imply them (e.g., 'Paris' implies France). "
            "If the new message does not clearly change a field, do not include that key. "
            "Resolve relative dates like 'tomorrow' or 'next Monday' into concrete ISO dates (YYYY-MM-DD) using the current datetime. "
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
            updates.update(changes)
            prospective_state = dict(snapshot)
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
