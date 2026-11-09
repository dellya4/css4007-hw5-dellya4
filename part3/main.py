import argparse
import json
import re
import shutil
from pathlib import Path

from dotenv import load_dotenv
from langchain_core.messages import HumanMessage, SystemMessage
from langchain_openai import ChatOpenAI
from langgraph.graph import StateGraph, START, END
from langgraph.graph.message import MessagesState
from langgraph.prebuilt import ToolNode, tools_condition
from langgraph.checkpoint.sqlite import SqliteSaver
from langgraph.errors import GraphRecursionError

from part2.tools import create_tools
from part3.memory import (
    STORAGE_DIR,
    PROJECT_DIR,
    UserMemory,
    extract_language_preference,
)

load_dotenv()

OUTPUT_DIR = PROJECT_DIR / "outputs"
SCENARIOS_FILE = PROJECT_DIR / "data" / "scenarios.json"

SYSTEM_PROMPT = """
You are a fictional university IT helpdesk assistant.

You help with Wi-Fi, password recovery, service status,
and local support ticket drafts.

Important rules:

- Use tools when necessary.
- Never invent troubleshooting steps or problem details.
- NEVER prepare a ticket unless the user explicitly asks
  for a ticket or clearly accepts an offer to create one.
- If the user only describes a problem, provide help
  or ask a follow-up question.
- Don't automatically create tickets.
- Never claim a ticket was sent to the university.
- For conditional tickets, check service status first.
- Never create conditional tickets if status is not operational.
- Never invent repair times.
- Never request passwords, API keys or recovery codes.

Memory rules:

- Remember the conversation history using saved checkpoints.
- Remember the user's preferred language.
- Use only the current user's stored memory.
- Never invent previous conversations or preferences.
- Don't confuse reference instructions with actions
  the user actually tried.
- Answer memory questions using saved information.
"""


def safe_text(value):
    """
    Avoid writing common secret formats to logs or memory.
    Do not enter real passwords or keys in this demo.
    """
    value = re.sub(
        r"\b(password|api_key|token)\s*[:=]\s*\S+",
        r"\1=[REDACTED]",
        value,
        flags=re.IGNORECASE,
    )
    value = re.sub(
        r"\bsk-[A-Za-z0-9_-]{12,}",
        "[REDACTED_KEY]",
        value,
    )
    return value


def serialize_message(message):
    result = {
        "type": message.type,
        "content": safe_text(str(message.content)),
    }

    if getattr(message, "name", None):
        result["name"] = message.name

    if getattr(message, "tool_calls", None):
        result["tool_calls"] = [
            {
                "name": call["name"],
                "args": call["args"],
            }
            for call in message.tool_calls
        ]

    return result


def build_agent(user_id, thread_id, profile, preference, saver):
    tools = create_tools(user_id, thread_id, profile)

    model = ChatOpenAI(
        model=__import__("os").environ.get(
            "MODEL_NAME", "gpt-4o-mini"
        ),
        temperature=0,
    ).bind_tools(tools)

    def assistant(state: MessagesState):
        if preference:
            memory_instruction = (
                f"The user's saved language preference is "
                f"{preference}. Respond in this language. "
                f"This preference came from user memory."
            )
        else:
            memory_instruction = (
                "There is no saved language preference "
                "for this user."
            )

        response = model.invoke(
            [
                SystemMessage(content=SYSTEM_PROMPT),
                SystemMessage(content=memory_instruction),
            ] + state["messages"]
        )

        return {"messages": [response]}

    workflow = StateGraph(MessagesState)

    workflow.add_node("assistant", assistant)
    workflow.add_node("tools", ToolNode(tools))

    workflow.add_edge(START, "assistant")

    workflow.add_conditional_edges(
        "assistant",
        tools_condition,
        {
            "tools": "tools",
            "__end__": END,
        },
    )

    workflow.add_edge("tools", "assistant")

    return workflow.compile(checkpointer=saver)


def run_turn(
    saver, user_memory, user_id, thread_id, profile, message
):
    message = safe_text(message)

    storage_thread_id = f"{user_id}::{thread_id}"

    config = {
        "configurable": {
            "thread_id": storage_thread_id
        },
        "recursion_limit": 16,
    }

    previous_preference = user_memory.get_language(user_id)

    detected_language = extract_language_preference(message)

    if detected_language:
        user_memory.save_language(user_id, detected_language)

    preference = user_memory.get_language(user_id)

    agent = build_agent(
        user_id, thread_id, profile, preference, saver
    )

    previous_state = agent.get_state(config).values
    previous_messages = previous_state.get("messages", [])

    sources = []

    if previous_messages:
        sources.append("conversation_memory")

    if preference:
        sources.append("user_memory")

    trace = []
    final_reply = ""
    limit_reached = False

    print(f"\nUSER [{user_id} / {thread_id}]: {message}")
    print("Previous messages:", len(previous_messages))
    print("Saved language:", preference or "None")

    try:
        for event in agent.stream(
            {
                "messages": [
                    HumanMessage(content=message)
                ]
            },
            config=config,
            stream_mode="updates",
        ):
            for node, update in event.items():
                messages = update.get("messages", [])

                record = {
                    "node": node,
                    "messages": [
                        serialize_message(m) for m in messages
                    ],
                }

                trace.append(record)
                print("\nNODE:", node)

                for item in messages:
                    if getattr(item, "tool_calls", None):
                        for call in item.tool_calls:
                            print(
                                "TOOL REQUEST:",
                                call["name"],
                                call["args"],
                            )

                    elif item.type == "tool":
                        print(
                            "TOOL RESULT:",
                            item.name,
                            safe_text(str(item.content)),
                        )

                        if item.name == "find_instructions":
                            if "helpdesk_reference" not in sources:
                                sources.append("helpdesk_reference")

                        if item.name == "check_service_status":
                            if "service_status_reference" not in sources:
                                sources.append("service_status_reference")

                    elif item.type == "ai" and item.content:
                        final_reply = safe_text(str(item.content))
                        print("AI:", final_reply)

    except GraphRecursionError:
        limit_reached = True
        final_reply = (
            "The graph reached its execution limit."
        )
        print("LOOP LIMIT REACHED")

    saved_state = agent.get_state(config).values
    saved_messages = saved_state.get("messages", [])

    return {
        "user_id": user_id,
        "thread_id": thread_id,
        "status_profile": profile,
        "message": message,
        "memory_read": {
            "conversation_messages_before": len(previous_messages),
            "user_preference_before": previous_preference,
            "user_preference_after": preference,
            "preference_updated": detected_language is not None,
        },
        "sources": sources,
        "trace": trace,
        "final_response": final_reply,
        "saved_messages_after": len(saved_messages),
        "loop_limit_reached": limit_reached,
    }


def load_scenario(scenario_id):
    with SCENARIOS_FILE.open("r", encoding="utf-8") as file:
        data = json.load(file)

    for scenario in data["scenarios"]:
        if scenario["id"] == scenario_id:
            if scenario["part"] != 3:
                raise ValueError("This is not a Part 3 scenario")
            return scenario

    raise ValueError(f"Unknown scenario: {scenario_id}")


def split_segments(events):
    segments = [[]]

    for event in events:
        if event["action"] == "restart_process":
            if not event.get("preserve_local_storage", False):
                raise ValueError(
                    "This runner expects preserved storage"
                )
            segments.append([])
        elif event["action"] == "message":
            segments[-1].append(event)
        else:
            raise ValueError(
                f"Unknown event action: {event['action']}"
            )

    return segments


def execute(
    scope, events, profile, reset=False,
    scenario_id=None, segment=None
):
    session_dir = STORAGE_DIR / "part3" / scope

    if reset and session_dir.exists():
        shutil.rmtree(session_dir)

    session_dir.mkdir(parents=True, exist_ok=True)

    checkpoint_file = session_dir / "checkpoints.sqlite"
    user_file = session_dir / "users.sqlite"

    results = []

    with SqliteSaver.from_conn_string(
        str(checkpoint_file)
    ) as saver:

        user_memory = UserMemory(user_file)

        try:
            for event in events:
                result = run_turn(
                    saver=saver,
                    user_memory=user_memory,
                    user_id=event["user_id"],
                    thread_id=event["thread_id"],
                    profile=profile,
                    message=event["message"],
                )
                results.append(result)
        finally:
            user_memory.close()

    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

    log_name = scenario_id or "manual"
    log_path = OUTPUT_DIR / f"{log_name}.json"

    if segment == 2 and log_path.exists():
        with log_path.open("r", encoding="utf-8") as file:
            log = json.load(file)
    else:
        log = {
            "scenario": log_name,
            "status_profile": profile,
            "storage": str(session_dir),
            "runs": [],
        }

    log["runs"].append({
        "segment": segment or 1,
        "events": results,
    })

    with log_path.open("w", encoding="utf-8") as file:
        json.dump(log, file, indent=2, ensure_ascii=False)

    print("\nLOG SAVED:", log_path)
    print("MEMORY SAVED:", session_dir)


def main():
    parser = argparse.ArgumentParser()

    parser.add_argument("--scenario")
    parser.add_argument("--segment", type=int)
    parser.add_argument("--user-id", default="demo-user-a")
    parser.add_argument("--thread-id", default="manual")
    parser.add_argument("--status-profile", default="normal")
    parser.add_argument("--message", action="append")

    args = parser.parse_args()

    if args.scenario:
        scenario = load_scenario(args.scenario)
        segments = split_segments(scenario["events"])

        if len(segments) > 1:
            if args.segment not in (1, 2):
                parser.error(
                    "This scenario requires --segment 1 "
                    "and --segment 2 in separate launches"
                )
            events = segments[args.segment - 1]
            reset = (
                args.segment == 1
                and scenario.get("reset_before", False)
            )
        else:
            if args.segment is not None:
                parser.error("This scenario has no restart")
            events = segments[0]
            reset = scenario.get("reset_before", False)

        execute(
            scope=args.scenario,
            events=events,
            profile=scenario["status_profile"],
            reset=reset,
            scenario_id=args.scenario,
            segment=args.segment,
        )

    elif args.message:
        events = [
            {
                "action": "message",
                "user_id": args.user_id,
                "thread_id": args.thread_id,
                "message": message,
            }
            for message in args.message
        ]

        execute(
            scope="manual",
            events=events,
            profile=args.status_profile,
        )

    else:
        parser.error("Provide --scenario or --message")


if __name__ == "__main__":
    main()
