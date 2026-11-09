from langchain_core.messages import HumanMessage, AIMessage
from langgraph.checkpoint.sqlite import SqliteSaver
from langgraph.graph import StateGraph, START, END
from langgraph.graph.message import MessagesState

from part3.memory import UserMemory


def make_fake_graph(saver):
    """A deterministic fake assistant without an LLM."""

    def fake_assistant(state: MessagesState):
        return {
            "messages": [
                AIMessage(content="Test reply")
            ]
        }

    graph = StateGraph(MessagesState)
    graph.add_node("assistant", fake_assistant)
    graph.add_edge(START, "assistant")
    graph.add_edge("assistant", END)

    return graph.compile(checkpointer=saver)


def config_for(user_id, thread_id):
    return {
        "configurable": {
            "thread_id": f"{user_id}::{thread_id}"
        }
    }


def test_conversation_survives_restart(tmp_path):
    db_path = tmp_path / "checkpoints.sqlite"
    config = config_for("demo-user-a", "thread-a")

    with SqliteSaver.from_conn_string(str(db_path)) as saver:
        graph = make_fake_graph(saver)

        graph.invoke({
            "messages": [
                HumanMessage(content="I have a Wi-Fi problem")
            ]
        }, config=config)

    with SqliteSaver.from_conn_string(str(db_path)) as saver:
        graph = make_fake_graph(saver)

        saved = graph.get_state(config).values["messages"]

        assert any(
            msg.content == "I have a Wi-Fi problem"
            for msg in saved
        )


def test_threads_are_separate(tmp_path):
    db_path = tmp_path / "checkpoints.sqlite"

    config_a = config_for("demo-user-a", "thread-1")
    config_b = config_for("demo-user-a", "thread-2")

    with SqliteSaver.from_conn_string(str(db_path)) as saver:
        graph = make_fake_graph(saver)

        graph.invoke({
            "messages": [
                HumanMessage(content="Private thread message")
            ]
        }, config=config_a)

        state_b = graph.get_state(config_b).values

        assert not state_b.get("messages", [])


def test_users_are_separate(tmp_path):
    db_path = tmp_path / "checkpoints.sqlite"

    config_a = config_for("demo-user-a", "shared-name")
    config_b = config_for("demo-user-b", "shared-name")

    with SqliteSaver.from_conn_string(str(db_path)) as saver:
        graph = make_fake_graph(saver)

        graph.invoke({
            "messages": [
                HumanMessage(content="User A problem")
            ]
        }, config=config_a)

        state_b = graph.get_state(config_b).values
        assert not state_b.get("messages", [])


def test_user_preference_persists(tmp_path):
    db_path = tmp_path / "users.sqlite"

    memory = UserMemory(db_path)
    memory.save_language("demo-user-a", "Kazakh")
    memory.close()

    memory = UserMemory(db_path)

    assert memory.get_language("demo-user-a") == "Kazakh"
    assert memory.get_language("demo-user-b") is None

    memory.close()
