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

    def __init__(self,id):
        Thread.__init__(self)
        self.id = id
        self.port = config.port+id
        self.daemon = True
        self.lamport_ts = 0

        self.server = NodeServer(self) 
        self.server.start()

        #TODO OPTIONAL This is a simple way to define the collegues, but it is not the best way to do it.
        # You can implement a more complex way to define the collegues, but for now this is enough.
        if id % 2 == 0:
            self.collegues = list(range(0,config.numNodes,2))
        else:
            self.collegues = list(range(1,config.numNodes,2))


        self.client = NodeSend(self)    

    def do_connections(self):
        self.client.build_connection()

    def run(self):
        print("Run Node%i with the follows %s"%(self.id,self.collegues))
        self.client.start()

        
        #TODO MANDATORY Change this loop to simulate the Maekawa algorithm to 
        # - Request the lock
        # - Wait for the lock
        # - Release the lock
        # - Repeat until some condition is met (e.g. timeout, wakeupcounter == 3)

        self.wakeupcounter = 0
        while self.wakeupcounter <= 2: # Termination criteria

            # Nodes with different starting times
            time_offset = random.randint(2, 8)
            time.sleep(time_offset) 
            
            # A dummy message
            print("This is Node_%i at TS:%i sending a message to my collegues"%(self.id,self.lamport_ts))
            self.lamport_ts += 1 # Increment the timestamp
            message = Message(msg_type="greetings",
                            src=self.id,
                            data="Hola, this is Node_%i _ counter:%i"%(self.id,self.wakeupcounter))

            self.client.multicast(message, self.collegues)


            # Control iteration 
            self.wakeupcounter += 1 
                
        # Wait for all nodes to finish
        print("Node_%i is waiting for all nodes to finish"%self.id)
        self._finished()

        print("Node_%i DONE!"%self.id)

    #TODO OPTIONAL you can change the way to stop
    def _finished(self): 
        with Node._HAVE_ALL_FINISHED:
            Node._FINISHED_NODES += 1
            if Node._FINISHED_NODES == config.numNodes:
                Node._HAVE_ALL_FINISHED.notify_all()

            while Node._FINISHED_NODES < config.numNodes:
                Node._HAVE_ALL_FINISHED.wait()