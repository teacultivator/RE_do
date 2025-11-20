from langchain_core.messages import HumanMessage
from graph.builder import build_graph

graph = build_graph()

# Use a fixed thread_id to simulate one conversation
config = {"configurable": {"thread_id": "demo-user"}}

# Turn 1
result1 = graph.invoke(
    {"messages": [HumanMessage(content="Flights from Paris to Delhi")]},
    config=config,
)
print(result1["messages"][-1].content)

# Turn 2 (same thread_id, new user message)
result2 = graph.invoke(
    {"messages": [HumanMessage(content="Also, make them non-stop")]},
    config=config,
)
print(result2["messages"][-1].content)

# Turn 3 (same thread_id again)
result3 = graph.invoke(
    {"messages": [HumanMessage(content="Actually, for next Monday")]},
    config=config,
)
print(result3["messages"][-1].content)