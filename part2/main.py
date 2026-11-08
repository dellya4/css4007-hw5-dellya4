import argparse
import json
import os
from pathlib import Path

from dotenv import load_dotenv
from langchain_core.messages import (
    HumanMessage,
    SystemMessage,
)
from langchain_openai import ChatOpenAI
from langgraph.graph import StateGraph, START, END
from langgraph.graph.message import MessagesState
from langgraph.prebuilt import ToolNode, tools_condition
from langgraph.errors import GraphRecursionError

from tools import create_tools

load_dotenv()

BASE_DIR = Path(__file__).resolve().parent.parent
OUTPUT_DIR = BASE_DIR / "outputs"

SYSTEM_PROMPT = """
You are a fictional university IT helpdesk assistant.

You help with Wi-Fi and password recovery.

Rules:
1. Use find_instructions to retrieve local instructions.
2. Use check_service_status for service status questions.
3. Use prepare_ticket only to create a LOCAL draft.
4. Never claim a draft was sent to the university.
5. Never invent troubleshooting steps or problem details.
6. If the problem or steps tried are missing, ask the user.
7. For a conditional request such as "create a ticket if
   the service is operating", check the status FIRST.
8. Set conditional_on_operational=True for such requests.
9. If status is outage, do not create a conditional ticket.
10. If status is unknown, do not create a conditional ticket.
    Explain uncertainty and offer a draft if requested.
11. Do not invent a repair time.
12. A password problem maps to the account_recovery service.
13. Do not request or store passwords or recovery codes.
14. Only describe tool results that were actually returned.
15. Follow the actual user's request, not imagined steps.
16. Call tools when needed, then provide a concise answer.
"""


def build_agent(user_id, thread_id, status_profile):
    tools = create_tools(
        user_id=user_id,
        thread_id=thread_id,
        status_profile=status_profile
    )

    model = ChatOpenAI(
        model=os.getenv("MODEL_NAME", "gpt-4o-mini"),
        temperature=0
    ).bind_tools(tools)

    def assistant(state: MessagesState):
        response = model.invoke(
            [SystemMessage(content=SYSTEM_PROMPT)]
            + state["messages"]
        )
        return {"messages": [response]}

    graph = StateGraph(MessagesState)

    graph.add_node("assistant", assistant)
    graph.add_node("tools", ToolNode(tools))

    graph.add_edge(START, "assistant")
    graph.add_conditional_edges(
        "assistant",
        tools_condition,
        {"tools": "tools", "__end__": END}
    )
    graph.add_edge("tools", "assistant")

    return graph.compile()


def run_message(agent, history, message, trace):
    input_messages = history + [HumanMessage(content=message)]
    new_messages = []
    final_reply = ""
    limit_reached = False

    print(f"\nUSER: {message}")

    try:
        for event in agent.stream(
            {"messages": input_messages},
            stream_mode="updates",
            config={"recursion_limit": 16}
        ):
            for node, update in event.items():
                messages = update.get("messages", [])

                trace.append({
                    "node": node,
                    "messages": [
                        serialize_message(m) for m in messages
                    ]
                })

                print(f"\nNODE: {node}")

                for item in messages:
                    new_messages.append(item)

                    if getattr(item, "tool_calls", None):
                        for call in item.tool_calls:
                            print(
                                "TOOL REQUEST:",
                                call["name"],
                                call["args"]
                            )

                    elif item.type == "tool":
                        print(
                            "TOOL RESULT:",
                            item.name, item.content
                        )

                    elif item.type == "ai" and item.content:
                        final_reply = str(item.content)
                        print("AI:", final_reply)

    except GraphRecursionError:
        limit_reached = True
        final_reply = (
            "The tool loop limit was reached. "
            "Please try a simpler request."
        )
        print("LOOP LIMIT REACHED")

    history.extend([HumanMessage(content=message)])
    history.extend(new_messages)

    return final_reply, limit_reached


def serialize_message(message):
    result = {
        "type": message.type,
        "content": str(message.content),
    }

    if getattr(message, "name", None):
        result["name"] = message.name

    if getattr(message, "tool_calls", None):
        result["tool_calls"] = message.tool_calls

    return result


def run_session(
    user_id,
    thread_id,
    status_profile,
    messages,
    scenario_id="manual"
):
    agent = build_agent(user_id, thread_id, status_profile)
    history = []
    trace = []
    responses = []
    limit_reached = False

    for message in messages:
        reply, hit_limit = run_message(
            agent, history, message, trace
        )
        responses.append(reply)
        limit_reached = limit_reached or hit_limit

    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

    log = {
        "scenario": scenario_id,
        "user_id": user_id,
        "thread_id": thread_id,
        "status_profile": status_profile,
        "messages": messages,
        "trace": trace,
        "responses": responses,
        "loop_limit_reached": limit_reached
    }

    filename = OUTPUT_DIR / f"{scenario_id}.json"

    with filename.open("w", encoding="utf-8") as file:
        json.dump(log, file, indent=2, ensure_ascii=False)

    print("\nLOG SAVED:", filename)


def main():
    parser = argparse.ArgumentParser()

    parser.add_argument("--scenario")
    parser.add_argument("--user-id", default="demo-user-a")
    parser.add_argument("--thread-id", default="manual")
    parser.add_argument("--status-profile", default="normal")
    parser.add_argument("--message", action="append")

    args = parser.parse_args()

    if args.scenario:
        with (
            BASE_DIR / "data" / "scenarios.json"
        ).open("r", encoding="utf-8") as file:
            scenarios = json.load(file)["scenarios"]

        selected = next(
            (s for s in scenarios if s["id"] == args.scenario),
            None
        )

        if not selected:
            parser.error("Unknown scenario")

        if selected["part"] != 2:
            parser.error("This runner is for Part 2 scenarios")

        events = [
            e for e in selected["events"]
            if e["action"] == "message"
        ]

        user_ids = {e["user_id"] for e in events}
        thread_ids = {e["thread_id"] for e in events}

        if len(user_ids) != 1 or len(thread_ids) != 1:
            parser.error("Multiple users/threads not supported here")

        run_session(
            user_id=events[0]["user_id"],
            thread_id=events[0]["thread_id"],
            status_profile=selected["status_profile"],
            messages=[e["message"] for e in events],
            scenario_id=selected["id"]
        )

    elif args.message:
        run_session(
            args.user_id,
            args.thread_id,
            args.status_profile,
            args.message
        )

    else:
        parser.error("Use --scenario or --message")


if __name__ == "__main__":
    main()
