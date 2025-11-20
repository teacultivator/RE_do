from typing import Dict, List

from langchain_core.messages import AIMessage, HumanMessage, BaseMessage

from graph.state import State


def _get_user_messages(messages: List[BaseMessage]) -> List[HumanMessage]:
    return [m for m in messages if isinstance(m, HumanMessage)]


def result_node(state: State) -> Dict:
    messages: List[BaseMessage] = list(state.get("messages", []))
    user_messages = _get_user_messages(messages)
    turn = len(user_messages)

    last_user = user_messages[-1].content if user_messages else "nothing yet"
    reply = f"This is turn {turn}. You just said: {last_user}"

    return {"messages": [AIMessage(content=reply)]}
