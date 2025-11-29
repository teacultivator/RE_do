from langchain_core.messages import HumanMessage
from graph.builder import build_graph


def main() -> None:
    graph = build_graph()
    config = {"configurable": {"thread_id": "demo-user"}}

    print("Type 'exit' to quit.\n")
    while True:
        text = input("You: ").strip()
        if not text:
            continue
        if text.lower() in {"exit", "quit"}:
            break

        result = graph.invoke(
            {"messages": [HumanMessage(content=text)]},
            config=config,
        )

        ai_msg = result["messages"][-1]
        print("Bot:", ai_msg.content)


if __name__ == "__main__":
    main()