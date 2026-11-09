import json

import pytest

import part2.tools as tool_module


@pytest.fixture
def tools_factory(tmp_path, monkeypatch):
    monkeypatch.setattr(
        tool_module, "STORAGE_DIR", tmp_path
    )

    def factory(profile="normal"):
        tools = tool_module.create_tools(
            "demo-user-a",
            "test-thread",
            profile
        )
        return {tool.name: tool for tool in tools}

    return factory


def test_find_instructions(tools_factory):
    tools = tools_factory()

    result = json.loads(
        tools["find_instructions"].invoke({
            "category": "wifi"
        })
    )

    assert result["instruction_id"] == "GUIDE-WIFI"
    assert len(result["steps"]) > 0


@pytest.mark.parametrize(
    "profile,expected",
    [
        ("normal", "operational"),
        ("wifi_outage", "outage"),
        ("status_unavailable", "unknown"),
    ]
)
def test_wifi_status(tools_factory, profile, expected):
    tools = tools_factory(profile)

    result = json.loads(
        tools["check_service_status"].invoke({
            "category": "wifi"
        })
    )

    assert result["status"] == expected


def test_account_recovery_status(tools_factory):
    tools = tools_factory("recovery_outage")

    result = json.loads(
        tools["check_service_status"].invoke({
            "category": "account_recovery"
        })
    )

    assert result["service"] == "account_recovery"
    assert result["status"] == "outage"


def test_ticket_created(tools_factory, tmp_path):
    tools = tools_factory()

    tools["check_service_status"].invoke({
        "category": "wifi"
    })

    result = json.loads(
        tools["prepare_ticket"].invoke({
            "category": "wifi",
            "summary": "Wi-Fi connection failed",
            "steps_tried": [
                "Enabled Wi-Fi",
                "Tried reconnecting"
            ],
            "conditional_on_operational": True
        })
    )

    assert result["ticket_created"] is True

    tickets = list((tmp_path / "tickets").glob("*.json"))
    assert len(tickets) == 1

    ticket = json.loads(tickets[0].read_text(
        encoding="utf-8"
    ))
    assert ticket["status"] == "draft"
    assert ticket["user_id"] == "demo-user-a"
    assert ticket["steps_tried"] == [
        "Enabled Wi-Fi",
        "Tried reconnecting"
    ]


@pytest.mark.parametrize(
    "profile",
    ["wifi_outage", "status_unavailable"]
)
def test_conditional_ticket_blocked(
    tools_factory, tmp_path, profile
):
    tools = tools_factory(profile)

    tools["check_service_status"].invoke({
        "category": "wifi"
    })

    result = json.loads(
        tools["prepare_ticket"].invoke({
            "category": "wifi",
            "summary": "Cannot connect to Wi-Fi",
            "steps_tried": ["Enabled Wi-Fi"],
            "conditional_on_operational": True
        })
    )

    assert result["ticket_created"] is False
    assert not list(tmp_path.rglob("TICKET-*.json"))


def test_missing_ticket_details(tools_factory):
    tools = tools_factory()

    result = json.loads(
        tools["prepare_ticket"].invoke({
            "category": "wifi",
            "summary": "",
            "steps_tried": []
        })
    )

    assert "error" in result
