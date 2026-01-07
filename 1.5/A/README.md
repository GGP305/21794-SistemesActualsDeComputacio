# Maekawa Mutex implementation

Implementation of Maekawa’s distributed mutual exclusion algorithm with Lamport timestamps. Four nodes form fixed quorums:
- Node0: {0,1,2}
- Node1: {0,1,3}
- Node2: {0,2,3}
- Node3: {1,2,3}

Each node spawns:
- `NodeServer` to accept TCP connections and dispatch inbound messages.
- `NodeSend` to maintain TCP clients and handle unicast/multicast sends.

### Protocol (message types)
- `REQUEST(ts, src → quorum)`: ask quorum members for permission. Sender increments its Lamport clock before multicast.
- `REPLY(ts, src → dest)`: grant permission. Only one outstanding grant per node; others are queued by timestamp then `src`.
- `RELEASE(ts, src → quorum)`: free the resource; receivers grant the next queued requester (if any) or clear `granted_to`.

Lamport clock updates happen on every send and on receipt of any message: `ts = max(local, remote) + 1`.

### Termination
Each node requests the critical section three times, then waits until all nodes finish (`Node._FINISHED_NODES`).

### How to run
```bash
python main.py
```
Expected: nodes enter the critical section in quorum order without timeouts; program exits with “Done”.

### Project files
- `main.py`: starts MaekawaMutex runner.
- `maekawaMutex.py`: builds nodes, starts them, waits for completion.
- `node.py`: node logic, state, Lamport clock, Maekawa handlers.
- `nodeServer.py`: TCP server; parses JSON and dispatches REQUEST/REPLY/RELEASE.
- `nodeSend.py`: TCP clients; unicast + multicast with timestamping.
- `message.py`: message DTO and JSON serialization.
- `config.py`: node count, base port.
- `utils.py`: socket helpers.

### References
- https://www.geeksforgeeks.org/maekawas-algorithm-for-mutual-exclusion-in-distributed-system/
- https://en.wikipedia.org/wiki/Maekawa%27s_algorithm
- https://github.com/yvetterowe/Maekawa-Mutex
- https://github.com/Sletheren/Maekawa-JAVA
- https://www.weizmann.ac.il/sci-tea/benari/software-and-learning-materials/daj-distributed-algorithms-java
