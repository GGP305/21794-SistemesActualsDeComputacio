from copy import deepcopy
from datetime import datetime, timedelta
from math import ceil, sqrt
from threading import Event, Thread, Timer
import utils
import config

# DONT MODIFY THIS CLASS
class NodeSend(Thread):
    def __init__(self, node):
        Thread.__init__(self)
        self.node = node
        self.client_sockets = [utils.create_client_socket() for i in range(config.numNodes)]
    
    def build_connection(self):
        for i in range(config.numNodes):
            self.client_sockets[i].connect(('localhost',config.port+i))
    
    def run(self):
        None

    def send_message(self, msg, dest, multicast=False):
        if not multicast:
            self.node.lamport_ts += 1
            msg.set_ts(self.node.lamport_ts)
        assert dest == msg.dest
        self.client_sockets[dest].sendall(bytes(msg.to_json(),encoding='utf-8'))


    def multicast(self, msg, group):
        self.node.lamport_ts += 1
        msg.set_ts(self.node.lamport_ts)
        for dest in group:
            new_msg = deepcopy(msg)
            new_msg.set_dest(dest)
            assert new_msg.dest == dest
            assert new_msg.ts == msg.ts
            self.send_message(new_msg, dest, True)

