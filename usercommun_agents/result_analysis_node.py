import json
import os
from typing import Dict, List

import google.generativeai as genai
from langchain_core.messages import AIMessage, BaseMessage, HumanMessage

from graph.state import State

genai.configure(api_key=os.environ.get("GOOGLE_API_KEY"))
_MODEL_NAME = os.getenv("GEMINI_MODEL_NAME", "gemini-2.0-flash")
_model = genai.GenerativeModel(_MODEL_NAME)


def _get_user_messages(messages: List[BaseMessage]) -> List[HumanMessage]:
    return [m for m in messages if isinstance(m, HumanMessage)]


def _clean_json_text(text: str) -> str:
    """Remove markdown code blocks if present."""
    text = text.strip()
    if text.startswith("```"):
        lines = text.splitlines()
        if len(lines) >= 2 and lines[0].startswith("```"):
            if lines[-1].startswith("```"):
                return "\n".join(lines[1:-1]).strip()
    return text


def result_analysis_node(state: State) -> Dict:
    """
    Analyze existing transport options based on user's followup request.
    This node is called when user asks about existing results without changing parameters.
    """
    messages: List[BaseMessage] = list(state.get("messages", []))
    user_messages = _get_user_messages(messages)
    
    if not user_messages:
        return {"messages": [AIMessage(content="No user message found.")]}
    
    followup_request = state.get("followup_request") or user_messages[-1].content
    
    # Collect available transport options
    flight_options = state.get("flight_options") or []
    bus_options = state.get("bus_options") or []
    train_options = state.get("train_options") or []
    
    # Determine which transport mode(s) we have results for
    available_modes = []
    if flight_options:
        available_modes.append("flights")
    if bus_options:
        available_modes.append("buses")
    if train_options:
        available_modes.append("trains")
    
    if not available_modes:
        return {
            "messages": [
                AIMessage(
                    content="No transport options available yet. Please wait for the search to complete."
                )
            ]
        }
    
    # Prepare context for LLM
    search_context = {
        "origin": state.get("origin", "Unknown"),
        "destination": state.get("destination", "Unknown"),
        "date": state.get("date", "Unknown"),
        "transport_mode": state.get("transport_mode", "Unknown"),
    }
    
    # Build prompt for analysis
    prompt = (
        "You are a helpful travel assistant analyzing existing travel search results.\n\n"
        f"Search context:\n"
        f"- Origin: {search_context['origin']}\n"
        f"- Destination: {search_context['destination']}\n"
        f"- Date: {search_context['date']}\n"
        f"- Transport mode: {search_context['transport_mode']}\n\n"
        f"User's followup question/request: {json.dumps(followup_request)}\n\n"
        f"Available results:\n"
    )
    
    # Add relevant transport options to the prompt
    if flight_options:
        prompt += f"\nFlight options ({len(flight_options)} available):\n"
        prompt += json.dumps(flight_options, ensure_ascii=False, indent=2)      
    if bus_options:
        prompt += f"\nBus options ({len(bus_options)} available):\n"
        prompt += json.dumps(bus_options, ensure_ascii=False, indent=2)
    if train_options:
        prompt += f"\nTrain options ({len(train_options)} available):\n"
        prompt += json.dumps(train_options, ensure_ascii=False, indent=2)
    
    prompt += (
        "\n\nAnalyze the user's request and provide a helpful response. "
        "This could involve:\n"
        "- Filtering or sorting options\n"
        "- Comparing different options\n"
        "- Finding cheapest/fastest/shortest options\n"
        "- Providing details about specific options\n"
        "- Answering questions about the available results\n\n"
        "Provide a clear, concise, and helpful response based on the available data. "
        "If the user asks for something that requires specific data not available in the results, "
        "politely explain what information is missing.\n\n"
        "Return only your analysis/response text, no JSON or code blocks."
    )
    
    try:
        response = _model.generate_content(prompt)
        analysis = getattr(response, "text", "") or ""
        analysis = _clean_json_text(analysis).strip()
        
        if not analysis:
            analysis = "I'm having trouble analyzing the results. Could you rephrase your question?"
        
        return {"messages": [AIMessage(content=analysis)]}
    
    except Exception as e:
        error_msg = f"Error analyzing results: {str(e)}"
        print(f"\n{error_msg}")
        return {
            "messages": [
                AIMessage(
                    content=f"I encountered an error while analyzing the results. Please try again or rephrase your question."
                )
            ]
        }

