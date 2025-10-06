#!/usr/bin/env python3
import json
import logging
import random
import secrets
import socket
import threading
import time
from datetime import datetime
from typing import Dict, List, Tuple


# ------------------------ Configuració del registre -----------------------
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    handlers=[
    logging.FileHandler("loteria_distribuida.log", encoding="utf-8"),
        logging.StreamHandler(),
    ],
)


# ---------------------------- Config de xarxa -----------------------------
# Fem servir multicast IPv4 per anunciar els resultats dels sortejos
DRAW_MULTICAST_GROUP = "224.0.0.1"  # multicast limitat a la subxarxa local
DRAW_MULTICAST_PORT = 56000

# Ports UDP unicast: els LAS escolten peticions de compra dels clients
LAS_BASE_PORT = 56100

# Els clients també obren un port UDP per rebre confirmacions i avisos de premi
CLIENT_BASE_PORT = 56200

BUFFER_SIZE = 4096


# ------------------------------- Missatges --------------------------------
# Convenció: JSON amb camps: type, sender, timestamp i camps específics
# (draw_id, number, client_id, ...)


def now_iso() -> str:
    return datetime.now().isoformat(timespec="seconds")


# --------------------------- Utilitats de sockets -------------------------
def make_udp_recv_socket(port: int, join_multicast: bool = False) -> socket.socket:
    s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM, socket.IPPROTO_UDP)
    s.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    s.bind(("", port))
    if join_multicast:
        group = socket.inet_aton(DRAW_MULTICAST_GROUP)
        mreq = group + socket.inet_aton("0.0.0.0")
        s.setsockopt(socket.IPPROTO_IP, socket.IP_ADD_MEMBERSHIP, mreq)
    return s


def make_udp_send_socket(multicast_ttl: int = 2) -> socket.socket:
    s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM, socket.IPPROTO_UDP)
    s.setsockopt(socket.IPPROTO_IP, socket.IP_MULTICAST_TTL, multicast_ttl)
    return s


# --------------------------------- DE ------------------------------------
class DrawEntity:
    """Realitza sortejos periòdicament i anuncia els resultats per multicast.

    Contracte breu:
        - Entrada: configuració (període i màxim de números)
        - Sortida: missatges JSON "DRAW_RESULT" cap al grup multicast amb draw_id
          i número guanyador
        - Errors: fallades de socket registrades; es pot aturar amb un flag
    """

    def __init__(self, period_sec: float = 5.0, max_number: int = 50):
        self.log = logging.getLogger("DE")
        self.period = period_sec
        self.max_number = max_number
        self.draw_id = 0
        self.running = True
        self.send_sock = make_udp_send_socket()

    def stop(self):
        self.running = False
        self.send_sock.close()

    def run(self, num_draws: int = 5):
        sysrand = secrets.SystemRandom()
        for _ in range(num_draws):
            if not self.running:
                break

            self.draw_id += 1
            winning = sysrand.randint(1, self.max_number)
            payload = {
                "type": "DRAW_RESULT",
                "sender": "DE",
                "timestamp": now_iso(),
                "draw_id": self.draw_id,
                "winning_number": winning,
                "max_number": self.max_number,
            }

            data = json.dumps(payload).encode("utf-8")
            self.send_sock.sendto(data, (DRAW_MULTICAST_GROUP, DRAW_MULTICAST_PORT))
            self.log.info(
                f"Anunciat sorteig #{self.draw_id} -> guanyador={winning} (1..{self.max_number})"
            )
            time.sleep(self.period)


# -------------------------------- LAS ------------------------------------
class Ticket:
    client_id: str
    client_addr: Tuple[str, int]
    draw_id: int
    number: int
    las_id: str


class LotteryAdminServer:
    """Vèn butlletes i notifica els guanyadors.

    - Escolta en un port UDP dedicat peticions BUY_TICKET
    - S'uneix al multicast del DE per rebre els resultats
    - En rebre un resultat, comprova totes les butlletes locals del sorteig
      i envia avisos de premi (WINNER_NOTIFICATION) per unicast
    """

    def __init__(self, las_index: int):
        self.las_index = las_index
        self.las_id = f"LAS-{las_index}"
        self.log = logging.getLogger(self.las_id)

        # Magatzem de butlletes: draw_id -> [Ticket, ...]
        self._tickets: Dict[int, List[Ticket]] = {}
        self._lock = threading.Lock()

        # Sockets: TCP per a compres, UDP multicast per a resultats
        self.purchase_port = LAS_BASE_PORT + las_index
        self.tcp_server = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self.tcp_server.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        self.tcp_server.bind(("", self.purchase_port))
        self.tcp_server.listen(8)
        self.recv_multicast_sock = make_udp_recv_socket(
            DRAW_MULTICAST_PORT, join_multicast=True
        )
        self.send_sock = make_udp_send_socket()

        # Cicle de vida
        self.running = True

    def stop(self):
        self.running = False
        for s in (self.tcp_server, self.recv_multicast_sock, self.send_sock):
            try:
                s.close()
            except Exception:
                pass

    # -------------------------- Compra de butlletes (TCP) ---------------
    def _handle_buy_ticket(self, msg: Dict, addr: Tuple[str, int], conn_file=None):
        client_id = msg.get("client_id")
        number = int(msg.get("number"))
        current_draw_id = int(msg.get("current_draw_id", 0))
        # El LAS no decideix el resultat; només registra la compra per al sorteig indicat
        t = Ticket(
            client_id=client_id,
            client_addr=(addr[0], int(msg.get("reply_port", addr[1]))),
            draw_id=current_draw_id,
            number=number,
            las_id=self.las_id,
        )
        with self._lock:
            self._tickets.setdefault(t.draw_id, []).append(t)
        self.log.info(
            f"Butlleta venuda a {client_id}: sorteig#{t.draw_id} número={t.number} (total={len(self._tickets.get(t.draw_id, []))})"
        )

        # Confirmació enviada per la mateixa connexió TCP (transacció fiable)
        if conn_file is not None:
            ack = {
                "type": "TICKET_CONFIRMED",
                "sender": self.las_id,
                "timestamp": now_iso(),
                "draw_id": t.draw_id,
                "number": t.number,
            }
            try:
                conn_file.write((json.dumps(ack) + "\n").encode("utf-8"))
                conn_file.flush()
            except Exception as e:
                self.log.error(f"Error enviant confirmació TCP: {e}")

    # ----------------------- Gestió de resultats ------------------------
    def _handle_draw_result(self, msg: Dict):
        draw_id = int(msg.get("draw_id"))
        winning = int(msg.get("winning_number"))
        with self._lock:
            tickets = list(self._tickets.get(draw_id, []))
        if not tickets:
            self.log.info(
                f"Rebut sorteig#{draw_id} -> {winning}; sense butlletes locals per a aquest sorteig"
            )
            return

        winners = [t for t in tickets if t.number == winning]
        self.log.info(
            f"Rebut sorteig#{draw_id} -> {winning}; {len(winners)} guanyador(s) local(s) de {len(tickets)}"
        )
        for t in winners:
            notif = {
                "type": "WINNER_NOTIFICATION",  # tipus de protocol en anglès
                "sender": self.las_id,
                "timestamp": now_iso(),
                "draw_id": draw_id,
                "number": winning,
            }
            try:
                self.send_sock.sendto(
                    json.dumps(notif).encode("utf-8"), (t.client_addr[0], t.client_addr[1])
                )
            except Exception as e:
                self.log.warning(f"Error en notificar {t.client_id}@{t.client_addr}: {e}")

    # ------------------------------ Fils ---------------------------------
    def _handle_purchase_connection(self, conn: socket.socket, addr: Tuple[str, int]):
        conn.settimeout(5.0)
        try:
            f = conn.makefile("rwb")
            line = f.readline()
            if not line:
                return
            msg = json.loads(line.decode("utf-8").strip())
            if msg.get("type") == "BUY_TICKET":
                self._handle_buy_ticket(msg, addr, conn_file=f)
        except Exception as e:
            self.log.error(f"Error connexió de compra TCP des de {addr}: {e}")
        finally:
            try:
                conn.close()
            except Exception:
                pass

    def _purchase_loop(self):
        self.tcp_server.settimeout(1.0)
        while self.running:
            try:
                conn, addr = self.tcp_server.accept()
            except socket.timeout:
                continue
            except OSError:
                break
            threading.Thread(
                target=self._handle_purchase_connection, args=(conn, addr), daemon=True
            ).start()

    def _multicast_loop(self):
        self.recv_multicast_sock.settimeout(1.0)
        while self.running:
            try:
                data, _ = self.recv_multicast_sock.recvfrom(BUFFER_SIZE)
            except socket.timeout:
                continue
            except OSError:
                break
            try:
                msg = json.loads(data.decode("utf-8"))
                if msg.get("type") == "DRAW_RESULT":
                    self._handle_draw_result(msg)
            except Exception as e:
                self.log.error(f"Error processant resultat de sorteig: {e}")

    def start(self) -> List[threading.Thread]:
        t1 = threading.Thread(target=self._purchase_loop, daemon=True)
        t2 = threading.Thread(target=self._multicast_loop, daemon=True)
        t1.start(); t2.start()
        return [t1, t2]


# -------------------------------- Client ---------------------------------
class Client:
    """Client de loteria que compra butlletes i escolta resultats.

    - Manté un socket UDP per rebre confirmacions i avisos de premi
    - Compra periòdicament una butlleta a un LAS aleatori per al sorteig actual
    - Opcionalment, s'uneix al multicast per observar els resultats del DE
    """

    def __init__(self, client_index: int, las_ports: List[int], max_number: int = 50):
        self.client_index = client_index
        self.client_id = f"Client-{client_index}"
        self.log = logging.getLogger(self.client_id)
        self.las_ports = las_ports
        self.max_number = max_number

        # socket del client per rebre avisos de premi (UDP)
        self.recv_port = CLIENT_BASE_PORT + client_index
        self.recv_sock = make_udp_recv_socket(self.recv_port)
        self.recv_sock.settimeout(1.0)

        # subscripció opcional al multicast per visualitzar resultats
        self.multicast_sock = make_udp_recv_socket(DRAW_MULTICAST_PORT, join_multicast=True)
        self.multicast_sock.settimeout(1.0)

        # socket UDP per si cal enviar altres missatges (no necessari per compra)
        self.send_sock = make_udp_send_socket()
        self.running = True

        # registre local de compres: (draw_id, number, las_port)
        self.purchases: List[Tuple[int, int, int]] = []

    def stop(self):
        self.running = False
        for s in (self.recv_sock, self.multicast_sock, self.send_sock):
            try:
                s.close()
            except Exception:
                pass

    def _buyer_loop(self, current_draw_getter, period_sec: float = 2.0):
        rnd = random.Random(1000 + self.client_index)  # determinista per client
        while self.running:
            draw_id = current_draw_getter()
            if draw_id <= 0:
                time.sleep(0.2)
                continue

            las_port = rnd.choice(self.las_ports)
            number = rnd.randint(1, self.max_number)
            # Compra via TCP (transacció fiable): enviar sol·licitud i llegir confirmació
            msg = {
                "type": "BUY_TICKET",
                "sender": self.client_id,
                "timestamp": now_iso(),
                "client_id": self.client_id,
                "reply_port": self.recv_port,
                "current_draw_id": draw_id,
                "number": number,
            }
            try:
                with socket.create_connection(("127.0.0.1", las_port), timeout=5.0) as sock:
                    f = sock.makefile("rwb")
                    f.write((json.dumps(msg) + "\n").encode("utf-8"))
                    f.flush()
                    line = f.readline()
                    if line:
                        ack = json.loads(line.decode("utf-8").strip())
                        if ack.get("type") == "TICKET_CONFIRMED":
                            self.log.info(
                                f"Confirmada: sorteig#{ack.get('draw_id')} número={ack.get('number')} (LAS {las_port})"
                            )
                        else:
                            self.log.warning("Resposta inesperada a la compra per TCP")
                    else:
                        self.log.warning("Sense confirmació TCP de compra")
            except Exception as e:
                self.log.error(f"Error en la compra TCP amb LAS {las_port}: {e}")
            self.log.info(f"Sol·licitada butlleta: sorteig#{draw_id} número={number} via TCP port {las_port}")
            self.purchases.append((draw_id, number, las_port))
            time.sleep(period_sec)

    def _recv_loop(self):
        while self.running:
            try:
                data, _ = self.recv_sock.recvfrom(BUFFER_SIZE)
            except socket.timeout:
                continue
            except OSError:
                break
            try:
                msg = json.loads(data.decode("utf-8"))
                t = msg.get("type")
                if t == "WINNER_NOTIFICATION":
                    self.log.warning(
                        f"PREMI! sorteig#{msg.get('draw_id')} número={msg.get('number')}"
                    )
            except Exception as e:
                self.log.error(f"Error de recepció del client: {e}")

    def _multicast_view_loop(self):
        while self.running:
            try:
                data, _ = self.multicast_sock.recvfrom(BUFFER_SIZE)
            except socket.timeout:
                continue
            except OSError:
                break
            try:
                msg = json.loads(data.decode("utf-8"))
                if msg.get("type") == "DRAW_RESULT":
                    self.log.info(
                        f"Observat resultat: #{msg.get('draw_id')} -> {msg.get('winning_number')}"
                    )
            except Exception as e:
                self.log.error(f"Error de multicast del client: {e}")

    def start(self, current_draw_getter) -> List[threading.Thread]:
        t1 = threading.Thread(target=self._buyer_loop, args=(current_draw_getter,), daemon=True)
        t2 = threading.Thread(target=self._recv_loop, daemon=True)
        t3 = threading.Thread(target=self._multicast_view_loop, daemon=True)
        t1.start(); t2.start(); t3.start()
        return [t1, t2, t3]


# ------------------------------- Orquestrador -----------------------------
def main(num_draws, num_las, num_clients, draw_period):
    print("Iniciant simulació de Loteria Distribuïda (TCP per compres, UDP per multicast)")

    # Crear DE
    de = DrawEntity(period_sec=draw_period, max_number=50)

    # Crear servidors LAS
    las_servers: List[LotteryAdminServer] = [LotteryAdminServer(i + 1) for i in range(num_las)]
    las_ports = [s.purchase_port for s in las_servers]

    # Getter compartit del draw_id vigent (mitjançant un fil observador)
    current_draw_lock = threading.Lock()
    current_draw_id = {"value": 0}

    # Petit ajudant que escolta el multicast per mantenir el draw_id autoritatiu
    def draw_tracker_loop():
        sock = make_udp_recv_socket(DRAW_MULTICAST_PORT, join_multicast=True)
        sock.settimeout(1.0)
        while True:
            try:
                data, _ = sock.recvfrom(BUFFER_SIZE)
                msg = json.loads(data.decode("utf-8"))
                if msg.get("type") == "DRAW_RESULT":
                    with current_draw_lock:
                        current_draw_id["value"] = int(msg.get("draw_id", 0))
            except socket.timeout:
                with current_draw_lock:
                    if current_draw_id.get("stop"):
                        break
                continue
            except Exception:
                break
        try:
            sock.close()
        except Exception:
            pass

    def get_current_draw():
        with current_draw_lock:
            return current_draw_id["value"]

    # Crear clients
    clients: List[Client] = [Client(i + 1, las_ports) for i in range(num_clients)]

    # Iniciar components
    threads: List[threading.Thread] = []
    # Fils dels LAS
    for las in las_servers:
        threads += las.start()

    # Fil seguidor del sorteig
    tracker_t = threading.Thread(target=draw_tracker_loop, daemon=True)
    tracker_t.start(); threads.append(tracker_t)

    # Clients
    for c in clients:
        threads += c.start(get_current_draw)

    # Executar el DE en primer pla (bloquejant) durant num_draws
    try:
        de.run(num_draws=num_draws)
    except KeyboardInterrupt:
        print("Interromput. Aturant...")
    finally:
        # Aturar clients i servidors de manera ordenada
        for c in clients:
            c.stop()
        for las in las_servers:
            las.stop()
        with current_draw_lock:
            current_draw_id["stop"] = True
        de.stop()
        # Esperar que els fils finalitzin
        for t in threads:
            t.join(timeout=2)
        print("Simulació completada.")


if __name__ == "__main__":
    main(num_draws=5, num_las=2, num_clients=5, draw_period=5.0)
