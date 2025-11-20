from typing import Any, Dict, List, Sequence
from typing_extensions import Annotated, TypedDict

from langchain_core.messages import BaseMessage
from langgraph.graph.message import add_messages


class State(TypedDict, total=False):
    messages: Annotated[Sequence[BaseMessage], add_messages]
    origin: str
    destination: str
    date: str
    transport_mode: str
    constraints: Dict[str, Any]
    flight_options: List[Dict[str, Any]]
    bus_options: List[Dict[str, Any]]
    train_options: List[Dict[str, Any]]
    final_answer: str
    needs: str


