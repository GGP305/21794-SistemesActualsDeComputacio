import select
from threading import Thread
import utils
from message import Message
import json

class NodeServer(Thread):
    def __init__(self, node):
        Thread.__init__(self)
        self.node = node
        self.daemon = True
    
    def run(self):
        self.update()

    def update(self):
        self.connection_list = []
        self.server_socket = utils.create_server_socket(self.node.port)
        self.connection_list.append(self.server_socket)

        while self.node.daemon:
            (read_sockets, write_sockets, error_sockets) = select.select(
                self.connection_list, [], [], 5)
            if not (read_sockets or write_sockets or error_sockets):
                print('NS%i - Timed out'%self.node.id) #force to assert the while condition 
            else:
                for read_socket in read_sockets:
                    if read_socket == self.server_socket:
                        (conn, addr) = read_socket.accept()
                        self.connection_list.append(conn)
                    else:
                        try:
                            msg_stream = read_socket.recvfrom(4096)
                            for msg in msg_stream:
                                try:
                                    ms = json.loads(str(msg,"utf-8"))
                                    self.process_message(ms)
                                except:
                                    None
                        except:
                            read_socket.close()
                            self.connection_list.remove(read_socket)
                            continue
        
        self.server_socket.close()

    def process_message(self, msg):
        msg_type = msg.get('msg_type')
        src = msg.get('src')

        print("Node_%i receive msg: %s"%(self.node.id,msg))

        if msg_type == 'REQUEST':
            self.node.handle_request(msg, src)
        elif msg_type == 'REPLY':
            self.node.handle_reply(msg, src)
        elif msg_type == 'RELEASE':
            self.node.handle_release(msg, src)
        else:
            # Unknown message types are ignored but still logged above
            pass

 