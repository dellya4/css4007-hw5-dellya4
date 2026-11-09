from part1 import build_graph


def run_graph(message, updated=False):
    graph = build_graph(updated=updated)

    return graph.invoke({
        "message": message,
        "category": "",
        "reply": ""
    })


def test_wifi_routing():
    result = run_graph("I cannot connect to Wi-Fi.")
    assert result["category"] == "wifi"
    assert "Campus-Demo" in result["reply"]


def test_password_case_insensitive():
    result = run_graph("I forgot my PASSWORD.")
    assert result["category"] == "password"
    assert "password" in result["reply"].lower()


def test_unknown_problem():
    result = run_graph("My laptop screen is broken.")
    assert result["category"] == "other"
    assert "Wi-Fi or a password" in result["reply"]


def test_original_wifi_priority():
    result = run_graph("My Wi-Fi password does not work.")
    assert result["category"] == "wifi"


def test_updated_clarification():
    result = run_graph(
        "My Wi-Fi password does not work.",
        updated=True
    )
    assert result["category"] == "both"
    assert "Wi-Fi" in result["reply"]
    assert "password" in result["reply"]
