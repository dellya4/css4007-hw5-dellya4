# HW5 — My LangGraph helpdesk

## Part 1 — How the graph works

### My graph and state

Graph: 

![Original Graph.png](graph/Original%20Graph.png)

| Node          | Reads                           | Changes       | 
|---------------|---------------------------------|---------------|
| read_request  | message                         | Sets category |
| wifi_help     | Wi-Fi instructions from JSON    | Sets reply    |
| password_help | Password instructions from JSON | Sets reply    |
| other_help    | No additional data              | Sets reply    |

The Wi-Fi and password instructions are loaded from `data/helpdesk.json`. The graph keeps the original message in the state and updates the category and reply step by step

**1. What information does each node read and change?**

`read_request` reads the user's message and sets the category. The help nodes read instructions from the local JSON file and set the reply. `other_help` returns a clarification question

**2. What is the difference between a node update and a conditional edge?**

A node updates the state. A conditional edge chooses which node runs next

**3. Does the next node receive only the update or the current graph state?**

The next node receives the current graph state, including the original message and previous updates

**4. What do START, END, and compiling a graph mean?**

`START` is the beginning of the graph. `END` finishes execution. Compiling prepares the graph so it can run

### Predictions before running

| Message                          | Predicted route               | Actual route                  | What I learned                    |
|----------------------------------|-------------------------------|-------------------------------|-----------------------------------|
| I cannot connect to Wi-Fi.       | read_request -> wifi_help     | read_request -> wifi_help     | Wi-Fi messages go to wifi_help    |
| I forgot my PASSWORD.            | read_request -> password_help | read_request -> password_help | Routing is case-insensitive       |
| My laptop screen is broken.      | read_request -> other_help    | read_request -> other_help    | Unknown problems go to other_help |
| My Wi-Fi password does not work. | read_request -> wifi_help     | read_request -> wifi_help     | Wi-Fi has priority over password  |

### My change to the graph

![Updated Graph.png](graph/Updated%20Graph.png)

```text


Message: My Wi-Fi password does not work.

Original graph:
read_request -> wifi_help -> END
Category: wifi
Result: Wi-Fi instructions

Updated graph:
read_request -> clarify_problem -> END

Node: read_request
Update: {"category": "both"}

Node: clarify_problem
Update:
{"reply": "Do you need help connecting to Wi-Fi, or recovering your account password?"}

Final category: both
Final reply:
Do you need help connecting to Wi-Fi,
or recovering your account password?

```

**Explain the difference**

In the original graph, Wi-Fi has priority. If a message contains both Wi-Fi and password, the graph goes to `wifi_help`
In the updated graph, I added a new node called `clarify_problem`. When both topics are found, the graph goes to this node and asks the user which problem they want to solve first
The updated graph has a new route, not just a different reply

**What does LangGraph control, and what do my functions decide?**

**LangGraph controls:**
- The order of node execution.
- The transitions between nodes.
- The graph state during execution.
- When the graph starts and ends.

**My Python functions decide:**
- Which category matches the message.
- Which route should be selected.
- Which instructions to retrieve from the JSON file.
- What reply to return.

### Execution Logs

- [Original graph — Wi-Fi](outputs/part1_original_01.json)
- [Original graph — password](outputs/part1_original_02.json)
- [Original graph — other](outputs/part1_original_03.json)
- [Original graph — both topics](outputs/part1_original_04.json)
- [Updated graph — both topics](outputs/part1_updated_01.json)

## Part 2 — Model and tools

**Model and tool loop**

![Model and tool loop.png](graph/Model%20and%20tool%20loop.png)

**Model and provider**

Provider: OpenAI

Model: gpt-4o-mini 

Framework: LangGraph

The model decides when to use tools. The tools read local JSON files or save ticket drafts

**1. How does the graph decide between running a tool and ending with an answer?**

The graph checks the model's response. If the model requests a tool, the graph goes to tools. If there is no tool request, the graph ends with the final answer

**2. Which component requests a tool, and which component actually executes it?**

The AI model requests a tool. LangGraph's ToolNode executes it and returns the result

**3. What changes in the state after a tool result returns?**

The tool result is added to the message state. The model can read this result and decide what to do next

**4. What makes this part different from the fixed routing rules in Part 1?**

Part 1 uses fixed Python rules to choose a route. Part 2 uses an AI model to choose tools and make decisions based on their results

Direct Tool Tests

I tested all three tools without the AI model using python part2/tools.py.

| Tool                 | Test                             | Result                               |
|----------------------|----------------------------------|--------------------------------------|
| find_instructions    | Find Wi-Fi instructions          | Returned instructions from GUIDE-WIF | 
| check_service_status | Check Wi-Fi using normal profile | Returned operational                 | 
| prepare_ticket       | Create a Wi-Fi ticket draft      | Saved a local JSON ticket            |

**Example Run - S06**

The user first requested Wi-Fi troubleshooting instructions. The assistant called find_instructions and returned the steps from the local guide.

The user then said that Wi-Fi still did not work and requested a ticket if the service was operating.

**Actual execution:**

1. assistant requested find_instructions with category wifi.

2. tools returned the GUIDE-WIFI instructions.

3. assistant returned the troubleshooting steps.

4. assistant requested check_service_status with category wifi.

5. tools returned status operational.

6. assistant requested prepare_ticket with the problem description and steps tried.

7. tools saved ticket TICKET-7BC87F22F6.json.

8. assistant confirmed that the ticket was saved locally and not sent.

The ticket contained the steps the user mentioned: enabling Wi-Fi, forgetting the saved network and trying to connect again

Different Status Profiles

| Scenario | Status profile     | Result                            | 
|----------|--------------------|-----------------------------------|
| S06      | normal             | Wi-Fi operational, ticket created |
| S07      | wifi_outage        | Wi-Fi outage, no ticket created   | 
| S08      | status_unavailable | Unknown status, no ticket created | 
| S14      | recovery_outage    | Account recovery outage reported  | 

The model used the selected status data instead of always creating a ticket

**Tool Loop Limit**

I set recursion_limit=16 in the LangGraph configuration.

This prevents the graph from running forever. If the graph reaches the limit, GraphRecursionError is caught and the program returns an error message

The limit was not reached in my successful scenario runs.

Execution Logs

* [S06](outputs/S06.json) - Operational Wi-Fi

* [S07](outputs/S07.json) - Wi-Fi outage

* [S08](outputs/S08.json) - Unknown status

* [S09](outputs/S09.json) - Missing ticket details

* [S14](outputs/S14.json) - Account recovery outage

All ticket drafts are saved locally. No real support tickets are submitted

## Part 3 — Memory

### How Memory Works

**Conversation State**

Conversation state stores the messages and tool results from the current conversation. I use LangGraph `SqliteSaver` to save this state in SQLite. It survives program restarts

**Thread ID**

`thread_id` identifies a specific conversation. Each thread has its own message history

**User Identifier**

`user_id` identifies a user. In my code, I use both `user_id` and `thread_id` to keep conversations separate

**User Preference Storage**

I use a separate SQLite database to store language preferences by `user_id`. The same preference is available in a new conversation for the same user

**Retrieval from helpdesk.json**

Retrieval means reading general instructions from `helpdesk.json` using `find_instructions`. This is different from memory because the instructions are reference data, not information remembered about a user

### Memory Tests

| Situation                   | Command used                                                                                            | Log file           | What happened                                                                           |
|-----------------------------|---------------------------------------------------------------------------------------------------------|--------------------|-----------------------------------------------------------------------------------------|
| Refer to an earlier message | `python -m part3.main --scenario S10`                                                                   | `outputs/S10.json` | The assistant remembered the Wi-Fi problem and the three steps already tried            |
| Close, restart and resume   | `python -m part3.main --scenario S11 --segment 1` and `python -m part3.main --scenario S11 --segment 2` | `outputs/S11.json` | The assistant loaded 4 previous messages after restart and remembered the Wi-Fi problem |
| Same user, new conversation | `python -m part3.main --scenario S12 --segment 1` and `python -m part3.main --scenario S12 --segment 2` | `outputs/S12.json` | A new thread had no previous messages, but the saved Kazakh preference was available    |
| Different user              | `python -m part3.main --scenario S13`                                                                   | `outputs/S13.json` | The second user had no previous messages or saved language preference                   |

### Where Memory Is Stored

Conversation and user memory are saved in `local-storage/part3/` as SQLite files

The program clears the scenario's memory before its first event when `reset_before` is true. It keeps the same storage between restart segments.

## Part 4 — Running and checking my work

TODO: point to the README setup steps, package versions, memory-reset instructions, tests and GitHub Actions workflow. Explain which mistake each test catches and which runs use a fake model.

## Choices and limitations

TODO: explain the storage and libraries I chose, why they fit this task, and what still does not work reliably.

## Supplied scenarios — my actual results

| Scenario | Command or manual steps | Log file | What happened / what I changed |
| --- | --- | --- | --- |
| S01 — Simple Wi-Fi route | | | |
| S02 — Case-insensitive password route | | | |
| S03 — Unsupported request | | | |
| S04 — Two topics before the graph change | | | |
| S05 — Two topics after adding clarification | | | |
| S06 — Instructions then local ticket | | | |
| S07 — The same request during a Wi-Fi outage | | | |
| S08 — Status source unavailable | | | |
| S09 — Missing ticket details | | | |
| S10 — Use the current conversation | | | |
| S11 — Persist and recall after restart | | | |
| S12 — Preference across threads without replay | | | |
| S13 — Do not share memory between users | | | |
| S14 — Password recovery outage | | | |
