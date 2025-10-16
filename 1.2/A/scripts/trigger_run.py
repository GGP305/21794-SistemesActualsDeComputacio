import sys
import time
import requests

BASE = "http://localhost:5001"  # trigger via agent1 by default

if __name__ == "__main__":
    round_no = int(sys.argv[1]) if len(sys.argv) > 1 else 1
    print(f"Triggering run at round {round_no} via agent1...")
    # give containers a moment to warm up if just started
    try:
        time.sleep(1.5)
        r = requests.post(f"{BASE}/run", json={"round": round_no}, timeout=3)
    except Exception as e:
        print(f"Trigger failed: {e}")
        sys.exit(1)
    r.raise_for_status()
    print(r.json())

    # Poll consensus from all agents
    agents = ["http://localhost:5001", "http://localhost:5002", "http://localhost:5003"]
    decided = False
    while True:
        statuses = []
        for a in agents:
            try:
                cr = requests.get(f"{a}/consensus", timeout=2.0)
                if cr.status_code == 200 and cr.json().get("reached"):
                    decided = True
                statuses.append((a, cr.status_code, cr.json()))
            except Exception as e:
                statuses.append((a, "err", str(e)))
        print(statuses)
        if decided:
            break
        time.sleep(.1)

    print("Done.")
