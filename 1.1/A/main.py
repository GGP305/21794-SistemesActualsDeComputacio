#!/usr/bin/env python3
"""
Sistemes Distribuïts - Comunicació de Grup amb Sockets
Una simulació de comunicació asíncrona entre agents mitjançant sockets UDP
"""

import socket
import threading
import time
import random
import json
import logging
from datetime import datetime
from typing import Dict

# Configuració del registre (logging)
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('comunicacio_agents.log', encoding='utf-8'),
        logging.StreamHandler()
    ]
)

# Configuració de xarxa
MULTICAST_GROUP = '224.0.0.1'  # Adreça multicast per a comunicació de grup
BASE_PORT = 5000
BUFFER_SIZE = 1024

class CommunicationAgent:
    """Classe base per a tots els agents de comunicació"""
    
    def __init__(self, agent_id: str, port: int):
        self.agent_id = agent_id
        self.port = port
        self.logger = logging.getLogger(f"Agent-{agent_id}")
    
        self.running = True
        
        # Crear socket UDP per rebre missatges
        self.recv_socket = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        self.recv_socket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        self.recv_socket.bind(('', port))
        
        # Unir-se al grup multicast per rebre missatges de difusió
        group = socket.inet_aton(MULTICAST_GROUP)
        mreq = group + socket.inet_aton('0.0.0.0')
        self.recv_socket.setsockopt(socket.IPPROTO_IP, socket.IP_ADD_MEMBERSHIP, mreq)
        
        # Crear socket UDP per enviar missatges
        self.send_socket = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        self.send_socket.setsockopt(socket.IPPROTO_IP, socket.IP_MULTICAST_TTL, 2)
        
    def send_message(self, message_type: str, content: str, request_id: int = None):
        """Envia un missatge al grup multicast"""
        message = {
            'sender': self.agent_id,
            'type': message_type,
            'content': content,
            'timestamp': datetime.now().isoformat(),
            'request_id': request_id
        }
        
        # Convertir a JSON i enviar
        msg_bytes = json.dumps(message).encode('utf-8')
        self.send_socket.sendto(msg_bytes, (MULTICAST_GROUP, BASE_PORT))

        # Mapar el tipus a una etiqueta en català només per al registre
        tipus_cat = {
            'HELP_REQUEST': 'PETICIÓ_AJUDA',
            'HELP_OK': 'AJUDA_SÍ',
            'HELP_NO': 'AJUDA_NO'
        }.get(message_type, message_type)

        self.logger.info(f"Enviat {tipus_cat}: {content} (Sol·licitud #{request_id})")
        
    def receive_messages(self):
        """Rep missatges contínuament des del socket"""
        while self.running:
            try:
                self.recv_socket.settimeout(1.0)
                data, addr = self.recv_socket.recvfrom(BUFFER_SIZE)
                message = json.loads(data.decode('utf-8'))
                
                # No processar els propis missatges
                if message['sender'] != self.agent_id:
                    self.handle_message(message)
                    
            except socket.timeout:
                continue
            except Exception as e:
                if self.running:
                    self.logger.error(f"Error rebent missatge: {e}")
                    
    def handle_message(self, message: Dict):
        """Sobreescriure als subclasses per gestionar tipus de missatges específics"""
        pass
        
    def stop(self):
        """Atura l'agent"""
        self.running = False
        self.recv_socket.close()
        self.send_socket.close()


class RequestingAgent(CommunicationAgent):
    """Agent que demana ajuda a altres"""
    
    def __init__(self, agent_id: str = "Sol·licitant", port: int = BASE_PORT):
        super().__init__(agent_id, port)
        self.current_request_id = 0
        self.help_responses = {}  # Seguiment de respostes per sol·licitud
        self.request_start_times = {}  # Instant d'inici de cada sol·licitud
        self.request_satisfied = {}  # Estat de satisfacció
        self.total_requests = 0
        self.satisfied_requests = 0
        
    def make_help_request(self):
        """Envia una petició d'ajuda a tots els agents"""
        self.current_request_id += 1
        self.total_requests += 1
        request_id = self.current_request_id
        
        # Inicialitzar seguiment per a aquesta sol·licitud
        self.help_responses[request_id] = 0
        self.request_start_times[request_id] = time.time()
        self.request_satisfied[request_id] = False
        
        # Enviar petició d'ajuda via multicast
        self.send_message("HELP_REQUEST", "#NecessitoAjuda!", request_id)
        
        # Programar una comprovació després d'un temps d'espera
        threading.Timer(5.0, self.check_request_satisfaction, args=[request_id]).start()
        
    def handle_message(self, message: Dict):
        """Gestiona les respostes dels agents ajudants"""
        if message['type'] in ['HELP_OK', 'HELP_NO']:
            request_id = message.get('request_id')
            
            if request_id and request_id in self.help_responses:
                if message['type'] == 'HELP_OK':
                    self.help_responses[request_id] += 1
                    self.logger.info(f"Rebuda AJUDA de {message['sender']} per a la Sol·licitud #{request_id}")
                    
                    # Comprovar si el quòrum (2 ajudes) està satisfet
                    if self.help_responses[request_id] >= 2 and not self.request_satisfied[request_id]:
                        self.request_satisfied[request_id] = True
                        self.satisfied_requests += 1
                        elapsed = time.time() - self.request_start_times[request_id]
                        self.logger.info(f"✓ Sol·licitud #{request_id} SATISFETA! (2 ajudants trobats en {elapsed:.2f}s)")
                else:
                    self.logger.info(f"Rebuda DENEGACIÓ de {message['sender']} per a la Sol·licitud #{request_id}")
                    
    def check_request_satisfaction(self, request_id: int):
        """Comprova si una sol·licitud s'ha satisfet després del temps d'espera"""
        if request_id in self.request_satisfied:
            if not self.request_satisfied[request_id]:
                self.logger.warning(f"✗ Sol·licitud #{request_id} NO SATISFETA (només {self.help_responses[request_id]} ajudants)")
                
    def run_periodic_requests(self, num_periods: int = 10):
        """Fa peticions d'ajuda periòdiques en intervals aleatoris"""
        for period in range(num_periods):
            if not self.running:
                break
                
            # Fer una petició d'ajuda
            self.make_help_request()
            
            # Esperar un interval aleatori (3-8 segons) abans de la següent
            wait_time = random.uniform(3.0, 8.0)
            time.sleep(wait_time)
            
        # Estadístiques finals
        time.sleep(5)  # Esperar les darreres respostes
        self.print_statistics()
        
    def print_statistics(self):
        """Imprimeix les estadístiques de satisfacció de quòrum"""
        satisfaction_rate = (self.satisfied_requests / self.total_requests * 100) if self.total_requests > 0 else 0
        
        self.logger.info("="*50)
        self.logger.info("ESTADÍSTIQUES DE SATISFACCIÓ DE QUÒRUM")
        self.logger.info(f"Total de sol·licituds fetes: {self.total_requests}")
        self.logger.info(f"Sol·licituds satisfetes: {self.satisfied_requests}")
        self.logger.info(f"Taxa de satisfacció: {satisfaction_rate:.1f}%")
        self.logger.info("="*50)
        

class HelperAgent(CommunicationAgent):
    """Agent que respon a peticions d'ajuda"""
    
    def __init__(self, agent_id: str, port: int = BASE_PORT):
        super().__init__(agent_id, port)
        
    def handle_message(self, message: Dict):
        """Gestiona peticions d'ajuda i decideix si ajudar"""
        if message['type'] == 'HELP_REQUEST':
            request_id = message.get('request_id')
            self.logger.info(f"Rebuda petició d'ajuda #{request_id} de {message['sender']}")
            
            # Simular temps de processament (0.5 a 3 segons)
            processing_time = random.uniform(0.5, 3.0)
            
            # Programar la resposta després del temps de processament
            threading.Timer(processing_time, self.respond_to_request, 
                          args=[message['sender'], request_id]).start()
            
    def respond_to_request(self, requester: str, request_id: int):
        """Decideix i envia la resposta segons probabilitats"""
        decision_rand = random.random()
        
        if decision_rand < 0.4:  # 40% de probabilitat d'ajudar
            self.send_message("HELP_OK", f"Dacord_{request_id}!", request_id)
            self.logger.info(f"Decidit AJUDAR per a la Sol·licitud #{request_id}")
            
        elif decision_rand < 0.9:  # 50% de probabilitat de denegar (0.4 + 0.5)
            self.send_message("HELP_NO", f"No_{request_id}!", request_id)
            self.logger.info(f"Decidit DENEGAR per a la Sol·licitud #{request_id}")
            
        else:  # 10% de probabilitat de no respondre
            self.logger.info(f"Decidit NO RESPONDRE per a la Sol·licitud #{request_id}")


def main():
    """Funció principal per executar la simulació del sistema distribuït"""
    print("Iniciant simulació de Sistema Distribuït - Comunicació de Grup")
    print("=" * 60)
    
    # Crear l'agent sol·licitant
    requestor = RequestingAgent()
    
    # Crear tres agents ajudants
    helpers = []
    for i in range(1, 4):
        helper = HelperAgent(f"Ajudant-{i}")
        helpers.append(helper)
        
    # Iniciar els fils de recepció de tots els agents
    threads = []
    
    # Receptor del sol·licitant
    requestor_thread = threading.Thread(target=requestor.receive_messages)
    requestor_thread.start()
    threads.append(requestor_thread)
    
    # Receptors dels ajudants
    for helper in helpers:
        helper_thread = threading.Thread(target=helper.receive_messages)
        helper_thread.start()
        threads.append(helper_thread)
        
    # Donar temps per inicialitzar
    time.sleep(1)
    
    try:
        # Executar la simulació amb peticions d'ajuda periòdiques
        print("Executant la simulació amb peticions d'ajuda periòdiques...")
        print("Consulteu 'comunicacio_agents.log' per als registres detallats")
        print("-" * 60)
        
        requestor.run_periodic_requests(num_periods=10)
        
    except KeyboardInterrupt:
        print("\nAturant la simulació...")
        
    finally:
        # Aturar tots els agents
        requestor.stop()
        for helper in helpers:
            helper.stop()
            
        # Esperar que acabin els fils
        for thread in threads:
            thread.join(timeout=2)
            
        print("\nSimulació completada!")


if __name__ == "__main__":
    main()