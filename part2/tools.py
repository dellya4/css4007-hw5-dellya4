import json
import os
import uuid
from copy import deepcopy
from pathlib import Path

from dotenv import load_dotenv
from langchain_core.tools import tool

load_dotenv()

BASE_DIR = Path(__file__).resolve().parent.parent
DATA_DIR = BASE_DIR / "data"

storage_setting = os.getenv(
    "HELPDESK_STORAGE_DIR", "local-storage"
)
STORAGE_DIR = Path(storage_setting)
if not STORAGE_DIR.is_absolute():
    STORAGE_DIR = BASE_DIR / STORAGE_DIR


def read_json(filename):
    with (DATA_DIR / filename).open(
        "r", encoding="utf-8"
    ) as file:
        return json.load(file)


HELPDESK = read_json("helpdesk.json")
STATUSES = read_json("service_status.json")["profiles"]
TEMPLATE = read_json("ticket_template.json")["ticket"]

VALID_CATEGORIES = ("wifi", "password")

def normalize_category(category: str) -> str:
    category = category.lower().strip()

    if category == "account_recovery":
        return "password"

    return category


def create_tools(user_id, thread_id, status_profile):
    """
    Create tools for one session.
    User ID, thread ID and profile are controlled
    by Python, not chosen by the AI model.
    """
    if status_profile not in STATUSES:
        raise ValueError(f"Unknown profile: {status_profile}")

    last_status = {}

    @tool
    def find_instructions(category: str) -> str:
        """Find local helpdesk instructions for wifi or password."""
        category = normalize_category(category)

        if category not in VALID_CATEGORIES:
            return json.dumps({
                "error": "Unknown category",
                "allowed": list(VALID_CATEGORIES)
            })

        data = HELPDESK["instructions"][category]

        return json.dumps({
            "category": category,
            "instruction_id": data["instruction_id"],
            "title": data["title"],
            "steps": data["steps"]
        })

    @tool
    def check_service_status(category: str) -> str:
        """Check the demo service status for wifi or password."""
        category = normalize_category(category)

        if category not in VALID_CATEGORIES:
            return json.dumps({
                "error": "Unknown category"
            })

        service = HELPDESK["topic_services"][category]
        result = STATUSES[status_profile][service]
        last_status[category] = result["status"]

        return json.dumps({
            "category": category,
            "service": service,
            "status": result["status"],
            "message": result["message"],
            "status_profile": status_profile
        })

    @tool
    def prepare_ticket(
        category: str,
        summary: str,
        steps_tried: list[str],
        conditional_on_operational: bool = False
    ) -> str:
        """
        Save a local support ticket draft.

        IMPORTANT:
        If the user asks to prepare a ticket ONLY IF the service
        is operational, you MUST set conditional_on_operational=True.

        Don't invent troubleshooting steps.
        """
        category = normalize_category(category)

        if category not in VALID_CATEGORIES:
            return json.dumps({
                "error": "Unknown ticket category"
            })

        if not summary.strip() or not steps_tried:
            return json.dumps({
                "error": "Missing problem or steps tried",
                "question": (
                    "What problem are you having, "
                    "and what have you already tried?"
                )
            })

        if not all(step.strip() for step in steps_tried):
            return json.dumps({
                "error": "Steps tried cannot be empty"
            })

        known_status = last_status.get(category)

        if conditional_on_operational:
            if known_status != "operational":
                return json.dumps({
                    "error": "Ticket condition not satisfied",
                    "service_status": known_status or "not_checked",
                    "ticket_created": False
                })

        ticket = deepcopy(TEMPLATE)
        ticket_id = f"TICKET-{uuid.uuid4().hex[:10].upper()}"

        ticket.update({
            "ticket_id": ticket_id,
            "status": "draft",
            "user_id": user_id,
            "thread_id": thread_id,
            "category": category,
            "summary": summary,
            "steps_tried": steps_tried,
            "service_status": known_status or "not_checked",
            "status_profile": (
                status_profile if known_status else None
            ),
            "reference_ids": []
        })

        tickets_dir = STORAGE_DIR / "tickets"
        tickets_dir.mkdir(parents=True, exist_ok=True)
        path = tickets_dir / f"{ticket_id}.json"

        with path.open("w", encoding="utf-8") as file:
            json.dump(
                ticket, file, ensure_ascii=False, indent=2
            )

        return json.dumps({
            "ticket_created": True,
            "ticket_id": ticket_id,
            "filename": str(path),
            "delivery": "local draft only"
        })

    return [
        find_instructions,
        check_service_status,
        prepare_ticket
    ]


if __name__ == "__main__":
    tools = create_tools(
        "demo-user-a", "tool-test", "normal"
    )

    print("INSTRUCTIONS:")
    print(tools[0].invoke({"category": "wifi"}))

    print("\nSERVICE STATUS:")
    print(tools[1].invoke({"category": "wifi"}))

    print("\nTICKET:")
    print(tools[2].invoke({
        "category": "wifi",
        "summary": "Demo Wi-Fi connection fails",
        "steps_tried": [
            "Enabled Wi-Fi",
            "Tried reconnecting"
        ],
        "conditional_on_operational": True
    }))
