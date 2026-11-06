import argparse
import json
from pathlib import Path
from typing import TypedDict

from langgraph.graph import StateGraph, START, END


BASE_DIR = Path(__file__).resolve().parent
DATA_FILE = BASE_DIR / "data" / "helpdesk.json"
OUTPUT_DIR = BASE_DIR / "outputs"

with DATA_FILE.open("r", encoding="utf-8") as file:
    HELPDESK_DATA = json.load(file)


class HelpdeskState(TypedDict):
    message: str
    category: str
    reply: str


def read_request(state: HelpdeskState, updated=False):
    message = state["message"].lower()

    has_wifi = "wifi" in message or "wi-fi" in message
    has_password = "password" in message

    if updated and has_wifi and has_password:
        category = "both"
    elif has_wifi:
        category = "wifi"
    elif has_password:
        category = "password"
    else:
        category = "other"

    return {"category": category}


# 4. Help nodes
def format_instructions(category):
    info = HELPDESK_DATA["instructions"][category]
    steps = "\n".join(
        f"{number}. {step}"
        for number, step in enumerate(info["steps"], start=1)
    )
    return f"{info['title']}\n{steps}"


def wifi_help(state: HelpdeskState):
    return {"reply": format_instructions("wifi")}


def password_help(state: HelpdeskState):
    return {"reply": format_instructions("password")}


def other_help(state: HelpdeskState):
    return {
        "reply": "Is your problem related to Wi-Fi or a password?"
    }


def clarify_problem(state: HelpdeskState):
    return {
        "reply": (
            "Do you need help connecting to Wi-Fi, "
            "or recovering your account password?"
        )
    }


def choose_next_node(state: HelpdeskState):
    routes = {
        "wifi": "wifi_help",
        "password": "password_help",
        "other": "other_help",
        "both": "clarify_problem",
    }
    return routes[state["category"]]


def build_graph(updated=False):
    workflow = StateGraph(HelpdeskState)

    workflow.add_node(
        "read_request",
        lambda state: read_request(state, updated)
    )
    workflow.add_node("wifi_help", wifi_help)
    workflow.add_node("password_help", password_help)
    workflow.add_node("other_help", other_help)

    routes = {
        "wifi": "wifi_help",
        "password": "password_help",
        "other": "other_help",
    }

    if updated:
        workflow.add_node("clarify_problem", clarify_problem)
        routes["both"] = "clarify_problem"

    workflow.add_edge(START, "read_request")

    workflow.add_conditional_edges(
        "read_request",
        choose_next_node,
        {node: node for node in routes.values()}
    )

    for node in routes.values():
        workflow.add_edge(node, END)

    return workflow.compile()


def predict_route(message, updated=False):
    state = {
        "message": message,
        "category": "",
        "reply": "",
    }
    update = read_request(state, updated)
    state.update(update)
    return ["read_request", choose_next_node(state)]


def run_message(graph, message, updated, run_number):
    state = {
        "message": message,
        "category": "",
        "reply": "",
    }

    prediction = predict_route(message, updated)
    print(f"\nMESSAGE: {message}")
    print("PREDICTED ROUTE:", " -> ".join(prediction))

    visited_nodes = []
    trace = []

    for event in graph.stream(state, stream_mode="updates"):
        for node_name, update in event.items():
            visited_nodes.append(node_name)
            state.update(update)

            record = {
                "node": node_name,
                "update": update,
                "state_after": state.copy(),
            }
            trace.append(record)

            print(f"\nNODE: {node_name}")
            print("UPDATE:", update)
            print("STATE:", state)

    print("\nACTUAL ROUTE:", " -> ".join(visited_nodes))
    print("\nHELPDESK REPLY:\n", state["reply"])

    result = {
        "part": 1,
        "graph_version": "updated" if updated else "original",
        "message": message,
        "predicted_route": prediction,
        "actual_route": visited_nodes,
        "prediction_matches": prediction == visited_nodes,
        "trace": trace,
        "final_response": state["reply"],
    }

    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    filename = (
        f"part1_{result['graph_version']}_{run_number:02d}.json"
    )
    output_path = OUTPUT_DIR / filename

    with output_path.open("w", encoding="utf-8") as file:
        json.dump(result, file, indent=2, ensure_ascii=False)

    print("\nTRACE SAVED:", output_path)


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--mode",
        choices=["original", "updated"],
        default="original",
    )
    parser.add_argument("--message", default=None)
    args = parser.parse_args()

    updated = args.mode == "updated"
    graph = build_graph(updated)

    if args.message:
        messages = [args.message]
    else:
        messages = [
            "I cannot connect to Wi-Fi.",
            "I forgot my PASSWORD.",
            "My laptop screen is broken.",
            "My Wi-Fi password does not work.",
        ]

    for number, message in enumerate(messages, start=1):
        run_message(graph, message, updated, number)
