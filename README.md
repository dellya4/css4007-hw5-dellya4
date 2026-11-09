# HW5 — University IT Helpdesk with LangGraph

This project is a terminal-based university IT helpdesk
built with Python and LangGraph.

The application uses fictional local data.

## Features

- Wi-Fi and password help
- AI tool calling
- Service status checking
- Local support ticket drafts
- Conversation memory
- User language preferences
- Persistent SQLite storage
- Automated tests

## Requirements

- Python 3.12
- An OpenAI API key for Parts 2 and 3

## Installation

Clone the repository and open the project folder.

Create a virtual environment:

```powershell
python -m venv .venv
```

Activate it on Windows:

```powershell
.\.venv\Scripts\Activate.ps1
```

Install dependencies:

```powershell
python -m pip install -r requirements.txt
```

## Environment Variables

Copy `.env.example` to `.env`.

Set the following values:

```env
OPENAI_API_KEY=your_api_key
MODEL_NAME=gpt-4o-mini
HELPDESK_STORAGE_DIR=local-storage
LANGSMITH_TRACING=false
```

Part 1 and the automated tests do not need an API key.

## Part 1 - Basic Graph

Run the original graph:

```powershell
python part1.py --mode original
```

Run the updated graph:

```powershell
python part1.py --mode updated
```

## Part 2 - Model and Tools

Test the tools without AI:

```powershell
python part2/tools.py
```

Run the scenarios:

```powershell
python -m part2.main --scenario S06
python -m part2.main --scenario S07
python -m part2.main --scenario S08
python -m part2.main --scenario S09
python -m part2.main --scenario S14
```

## Part 3 - Memory

Run conversation memory:

```powershell
python -m part3.main --scenario S10
```

Run the restart demonstration in two separate launches:

```powershell
python -m part3.main --scenario S11 --segment 1
python -m part3.main --scenario S11 --segment 2
```

Run user preference memory:

```powershell
python -m part3.main --scenario S12 --segment 1
python -m part3.main --scenario S12 --segment 2
```

Run user isolation:

```powershell
python -m part3.main --scenario S13
```

## Storage

Ticket drafts are saved in:

`local-storage/tickets/`

Persistent conversation and user memory is saved in:

`local-storage/part3/`

Scenario logs are saved in:

`outputs/`

To reset a test scenario, delete its folder inside
`local-storage/part3/` before running it again.

For restart scenarios, do not delete storage between
segment 1 and segment 2.

The scenario runner also resets memory automatically
when the selected scenario has `reset_before=true`.

## Automated Tests

Run all tests:

```powershell
python -m pytest tests/ -v
```

The tests do not require an OpenAI API key.

GitHub Actions runs these tests automatically after
pushing changes.

## Safety

All data is fictional.

The application does not connect to real university
systems or send support tickets.

API keys and local memory databases are not committed
to GitHub.