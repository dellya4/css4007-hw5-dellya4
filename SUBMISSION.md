# HW5 — My LangGraph helpdesk

## Part 1 — How the graph works

### My graph and state

Graph: 

![Original Graph.png](graph/Original%20Graph.png)

### Predictions before running

| Node          | Reads                           | Changes       | 
|---------------|---------------------------------|---------------|
| read_request  | message                         | Sets category |
| wifi_help     | Wi-Fi instructions from JSON    | Sets reply    |
| password_help | Password instructions from JSON | Sets reply    |
| other_help    | No additional data              | Sets reply    |

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

## Part 2 — Model and tools

TODO: draw the model/tool loop. Answer the four questions in the brief. Record the model and provider, direct calls to each tool, and one actual run that uses multiple tools. Explain the loop limit.

## Part 3 — Memory

TODO: explain conversation state, thread_id, user identifier, user preference storage, and retrieval from helpdesk.json.

| Situation | Command used | Log file | What happened |
| --- | --- | --- | --- |
| Refer to an earlier message | | | |
| Close, restart and resume | | | |
| Same user, new conversation | | | |
| Different user | | | |

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
