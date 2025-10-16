# Distributed Systems: RESTful consensus demo

This project simulates asynchronous communication between 3 agents using a RESTful API built with Flask. Each agent repeatedly proposes a random number until a majority (2 out of 3) agree. The number of attempts and the round at which consensus is reached are recorded.

## How it works

- Every agent exposes the same endpoints and is configured by environment variables (AGENT_ID, PORT, PEERS).
- A run starts when someone calls `/run` (or `/new_round`) on any agent. That agent broadcasts a new round to all peers (including itself) and each agent:
  - generates a random value,
  - posts a `/proposal` to others, and
  - waits briefly to tally proposals.
- If the same value is seen from a majority of agents, consensus is finalized (`/final` is broadcast). Otherwise, a new round begins automatically.

### Endpoints
- `POST /run` body: `{ "round": 1 }` — convenience to start a run from any node (automatically resets all agents first)
- `POST /reset` — clears all state (consensus, attempts, proposals) to allow a fresh run
- `POST /new_round` body: `{ "round": N }` — start round N locally and trigger local proposing
- `POST /proposal` body: `{ "agent_id": "agent1", "value": 2, "round": N }`
- `POST /final` body: `{ "value": V, "round": N }` — notify peers a decision has been made
- `GET /consensus` — returns 202 until decided, then 200 with `{ reached, value, round, attempts }`
- `GET /state` — returns local node state for debugging

## Message exchange and roles

- Any agent can initiate a run via `/run`, which first resets all agent state, then broadcasts `/new_round` to all.
- Communication is asynchronous and idempotent. Late/early proposals are ignored via round numbers.
- A small wait window is used to accumulate proposals; if no decision is reached, agents increment the round and try again.
- When consensus is detected (majority match), the agent broadcasts `/final` to peers and all agents stop generating new proposals.
- The `/run` endpoint ensures each trigger starts fresh by calling `/reset` on all agents first.

## Suitability discussion

REST suits simple, loosely coupled negotiations where:
- participants can tolerate eventual consistency; and
- the system favors simplicity over strong guarantees.

Caveats vs. real consensus (e.g., Raft/Paxos):
- No leader election or strict log/term guarantees
- No fault-tolerance beyond best-effort retries
- Possibility of live-lock without randomness bounds (mitigated here by tiny value range)

This demo is educational and not a production consensus algorithm.

## Run with Docker (recommended)

1. Build and launch the three agents:

```powershell
# from this folder
docker compose up --build
```

2. Trigger a run and observe consensus:

```powershell
python .\scripts\trigger_run.py
```

3. Inspect node states:

- http://localhost:5001/state
- http://localhost:5002/state
- http://localhost:5003/state

Stop with `Ctrl+C` and `docker compose down`.

## Run locally without Docker

```powershell
# create venv (Windows PowerShell)
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt

# start three terminals
$env:AGENT_ID="agent1"; $env:PORT=5001; $env:PEERS="http://localhost:5002,http://localhost:5003"; python -m agent.app
$env:AGENT_ID="agent2"; $env:PORT=5002; $env:PEERS="http://localhost:5001,http://localhost:5003"; python -m agent.app
$env:AGENT_ID="agent3"; $env:PORT=5003; $env:PEERS="http://localhost:5001,http://localhost:5002"; python -m agent.app

# in another terminal
python .\scripts\trigger_run.py 1
```

## Docker Compose packaging

The provided `docker-compose.yml` creates three services (`agent1`, `agent2`, `agent3`) on the same network so they can address each other by name. Publish ports 5001-5003 for local access.

## Notes

- The value range is small (1..3) to converge quickly; adjust via code if desired.
- Network failures are tolerated best-effort (short timeouts, ignore errors); persistent failures may prevent consensus.
- Attempts count increments on each fresh local proposal.
