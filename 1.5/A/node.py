from threading import Event, Thread, Timer, Condition
from datetime import datetime, timedelta
import time
from nodeServer import NodeServer
from nodeSend import NodeSend
from message import Message
import config
import random 

class Node(Thread):
    _FINISHED_NODES = 0
    _HAVE_ALL_FINISHED = Condition()
    _QUORUMS = [
        {0, 1, 2},
        {0, 1, 3},
        {0, 2, 3},
        {1, 2, 3},
    ]

    def __init__(self,id):
        Thread.__init__(self)
        self.id = id
        self.port = config.port+id
        self.daemon = True
        self.lamport_ts = 0

        self.server = NodeServer(self) 
        self.server.start()
        self.quorum = list(Node._QUORUMS[id])
        self.client = NodeSend(self)

        # Maekawa state
        self.granted_to = None
        self.request_queue = []
        self.reply_received = set()
        self.reply_condition = Condition()
        self.state_lock = Condition()
        self.in_critical_section = False
        self.pending_replies = set()

    def do_connections(self):
        self.client.build_connection()

    def run(self):
        print("Run Node%i with the follows %s"%(self.id,self.quorum))
        self.client.start()
        self.wakeupcounter = 0
        while self.wakeupcounter <= 2: # Termination criteria
            time_offset = random.randint(2, 8)
            time.sleep(time_offset)

            self.request_access()

            print("Node_%i is in CRITICAL SECTION (counter: %i)" % (self.id, self.wakeupcounter))
            time.sleep(1)

            self.release_access()
            self.wakeupcounter += 1

        print("Node_%i is waiting for all nodes to finish"%self.id)
        self._finished()
        print("Node_%i DONE!"%self.id)

    def _update_ts(self, other_ts):
        self.lamport_ts = max(self.lamport_ts, other_ts or 0) + 1

    def request_access(self):
        self.pending_replies = set(self.quorum)
        self.reply_received = set()
        request_msg = Message(msg_type="REQUEST", src=self.id)
        self.client.multicast(request_msg, self.quorum)

        with self.reply_condition:
            while len(self.reply_received) < len(self.quorum):
                self.reply_condition.wait()
        self.in_critical_section = True

    def release_access(self):
        self.in_critical_section = False
        release_msg = Message(msg_type="RELEASE", src=self.id)
        self.client.multicast(release_msg, self.quorum)
        with self.reply_condition:
            self.pending_replies = set()
            self.reply_received = set()

    def handle_request(self, msg, src):
        self._update_ts(msg.get('ts'))
        ts = msg.get('ts') or self.lamport_ts
        with self.state_lock:
            if self.granted_to is None:
                self.granted_to = src
                self._send_reply(src)
            else:
                if (ts, src) not in self.request_queue:
                    self.request_queue.append((ts, src))
                    self.request_queue.sort()

    def handle_reply(self, msg, src):
        self._update_ts(msg.get('ts'))
        with self.reply_condition:
            self.reply_received.add(src)
            if len(self.reply_received) >= len(self.quorum):
                self.reply_condition.notify_all()

    def handle_release(self, msg, src):
        self._update_ts(msg.get('ts'))
        with self.state_lock:
            if self.request_queue:
                self.request_queue.sort()
                _, next_src = self.request_queue.pop(0)
                self.granted_to = next_src
                self._send_reply(next_src)
            else:
                self.granted_to = None

    def _send_reply(self, dest):
        reply = Message(msg_type="REPLY", src=self.id, dest=dest)
        self.client.send_message(reply, dest)

    #TODO OPTIONAL you can change the way to stop
    def _finished(self): 
        with Node._HAVE_ALL_FINISHED:
            Node._FINISHED_NODES += 1
            if Node._FINISHED_NODES == config.numNodes:
                Node._HAVE_ALL_FINISHED.notify_all()

            while Node._FINISHED_NODES < config.numNodes:
                Node._HAVE_ALL_FINISHED.wait()