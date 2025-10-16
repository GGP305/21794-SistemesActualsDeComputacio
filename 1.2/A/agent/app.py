import os
import random
import threading
import time
from collections import Counter
from typing import Dict, List, Optional, Set

import requests
from flask import Flask, jsonify, request

# Simple RESTful agent that participates in a majority-consensus on a random number.
# Three agents exchange proposals asynchronously until at least 2/3 match.
# Configured via env vars: AGENT_ID, PORT, PEERS (comma-separated http base urls)

app = Flask(__name__)

AGENT_ID = os.getenv("AGENT_ID", "agent")
PORT = int(os.getenv("PORT", "5000"))
# peers are like: http://agent1:5000,http://agent2:5000
PEERS = [p for p in os.getenv("PEERS", "").split(",") if p]

# Shared state protected by a lock because Flask can be multithreaded
state_lock = threading.RLock()
current_round = 0
my_value: Optional[int] = None
proposals: Dict[str, int] = {}  # agent_id -> value
attempts = 0
consensus_value: Optional[int] = None
consensus_round: Optional[int] = None
started_rounds: Set[int] = set()  # rounds for which this agent already started _run_round

MAJORITY = 2  # for 3 agents
VALUE_RANGE = (1, 10000)  # small range to show convergence quickly


def reset_round(new_round: int):
    global current_round, my_value, proposals
    with state_lock:
        current_round = new_round
        my_value = None
        proposals = {}


def tally_and_check_consensus() -> Optional[int]:
    with state_lock:
        if not proposals:
            return None
        counts = Counter(proposals.values())
        value, cnt = counts.most_common(1)[0]
        if cnt >= MAJORITY:
            return value
        return None


@app.get("/state")
def get_state():
    with state_lock:
        return jsonify({
            "agent_id": AGENT_ID,
            "round": current_round,
            "my_value": my_value,
            "proposals": proposals,
            "attempts": attempts,
            "consensus_value": consensus_value,
            "consensus_round": consensus_round,
        })


@app.post("/new_round")
def new_round():
    global current_round, my_value, proposals, started_rounds, consensus_value
    data = request.get_json(silent=True) or {}
    round_no = int(data.get("round", 0))

    with state_lock:
        # If we've already decided, ignore further rounds
        if consensus_value is not None:
            return jsonify({"status": "ignored", "reason": "already-decided"}), 409

        # Ignore stale rounds
        if round_no < current_round:
            return jsonify({"status": "ignored", "reason": "stale-round", "current_round": current_round})

        # If this exact round already started locally, do not start another thread
        if round_no == current_round and round_no in started_rounds:
            return jsonify({"status": "already-started", "round": round_no})

        # Move to the requested round if needed and start once
        if round_no != current_round:
            # move to the requested round and clear per-round state
            current_round = round_no
            my_value = None
            proposals.clear()

        started_rounds.add(round_no)

    # Start proposing asynchronously to peers (outside lock)
    threading.Thread(target=_run_round, args=(round_no,), daemon=True).start()
    return jsonify({"status": "started", "round": round_no})


@app.post("/proposal")
def receive_proposal():
    data = request.get_json(force=True)
    sender = data["agent_id"]
    value = int(data["value"])  # value proposed by sender for current round
    round_no = int(data["round"])  # sender's round

    with state_lock:
        # Ignore late/early proposals
        if round_no != current_round:
            return jsonify({"status": "ignored", "reason": "round-mismatch", "current_round": current_round})
        proposals[sender] = value
        decided = tally_and_check_consensus()

    if decided is not None:
        _finalize_consensus(decided, round_no)
    return jsonify({"status": "ok"})


@app.get("/consensus")
def get_consensus():
    with state_lock:
        if consensus_value is None:
            return jsonify({"reached": False, "round": current_round}), 202
        return jsonify({"reached": True, "value": consensus_value, "round": consensus_round, "attempts": attempts})


@app.post("/reset")
def reset_state():
    # Reset all state to allow a fresh run
    global current_round, my_value, proposals, attempts, consensus_value, consensus_round, started_rounds
    with state_lock:
        current_round = 0
        my_value = None
        proposals = {}
        attempts = 0
        consensus_value = None
        consensus_round = None
        started_rounds.clear()
    return jsonify({"status": "reset"})


@app.post("/run")
def start_run():
    # convenience endpoint to trigger a run from any agent; this will ask all agents to start round 1
    data = request.get_json(silent=True) or {}
    start_round = int(data.get("round", 1))
    
    # First reset state on all agents
    for peer in PEERS:
        try:
            requests.post(f"{peer}/reset", timeout=1)
        except requests.RequestException:
            pass
    # Also reset locally
    global current_round, my_value, proposals, attempts, consensus_value, consensus_round, started_rounds
    with state_lock:
        current_round = 0
        my_value = None
        proposals = {}
        attempts = 0
        consensus_value = None
        consensus_round = None
        started_rounds.clear()
    
    # Now start the new run
    _broadcast_new_round(start_round)
    return jsonify({"status": "triggered", "round": start_round})


def _broadcast_new_round(round_no: int):
    global current_round, my_value, proposals, started_rounds, consensus_value
    # Don't start new round if consensus already reached; avoid duplicate starts
    start_locally = False
    with state_lock:
        if consensus_value is not None:
            return
        if round_no < current_round:
            return
        if round_no == current_round and round_no in started_rounds:
            start_locally = False
        else:
            if round_no != current_round:
                current_round = round_no
                my_value = None
                proposals.clear()
            started_rounds.add(round_no)
            start_locally = True

    # Broadcast to peers (fire-and-forget)
    for peer in PEERS:
        try:
            requests.post(f"{peer}/new_round", json={"round": round_no}, timeout=1)
        except requests.RequestException:
            pass

    # also run locally (only once per round)
    if start_locally:
        threading.Thread(target=_run_round, args=(round_no,), daemon=True).start()


def _run_round(round_no: int):
    global attempts, my_value
    # Check if consensus already reached (stop early)
    with state_lock:
        if consensus_value is not None:
            return
        if round_no != current_round:
            return
    
    # generate my value
    with state_lock:
        if consensus_value is not None:  # double-check after releasing lock
            return
        # Only increment attempts when we actually generate a new value for this round
        my_value = random.randint(*VALUE_RANGE)
        proposals[AGENT_ID] = my_value
        my_choice = my_value
        attempts += 1
        attempts_local = attempts
        print(f"[{AGENT_ID}] Round {round_no}, Attempt {attempts_local}, Value {my_choice}", flush=True)

    # send to peers
    for peer in PEERS:
        try:
            requests.post(f"{peer}/proposal", json={"agent_id": AGENT_ID, "value": my_choice, "round": round_no}, timeout=1)
        except requests.RequestException:
            pass

    # wait briefly for responses, then evaluate
    deadline = time.time() + 0.2
    while time.time() < deadline:
        # Check if another agent finalized consensus
        with state_lock:
            if consensus_value is not None:
                return
        decided = tally_and_check_consensus()
        if decided is not None:
            _finalize_consensus(decided, round_no)
            return
        time.sleep(0.05)

    # if no consensus, start a new round with new number
    with state_lock:
        if consensus_value is not None:  # final check before starting new round
            return
        decided = tally_and_check_consensus()
    if decided is not None:
        _finalize_consensus(decided, round_no)
        return

    # start next round
    next_round = round_no + 1
    _broadcast_new_round(next_round)


def _finalize_consensus(value: int, round_no: int):
    global consensus_value, consensus_round
    with state_lock:
        if consensus_value is not None:
            return  # already decided
        consensus_value = value
        consensus_round = round_no
    # notify peers (idempotent)
    for peer in PEERS:
        try:
            requests.post(f"{peer}/final", json={"value": value, "round": round_no}, timeout=1)
        except requests.RequestException:
            pass


@app.post("/final")
def receive_final():
    data = request.get_json(force=True)
    value = int(data["value"])  # decided value
    round_no = int(data["round"])  # decided round
    with state_lock:
        # accept the final decision if we haven't yet
        global consensus_value, consensus_round
        if consensus_value is None:
            consensus_value = value
            consensus_round = round_no
    return jsonify({"status": "ack"})


if __name__ == "__main__":
    # Use waitress production server for simplicity in Docker/non-debug
    from waitress import serve
    serve(app, host="0.0.0.0", port=PORT)
