from typing import Dict, List

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

    reply = f"This is turn {turn}. You just said: {last_user}. {prev_part}"

    return {"messages": [AIMessage(content=reply)]}
