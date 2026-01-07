"""
Demostración ligera de comunicación grupal indirecta (PUB/SUB) con sockets y un cliente CLI de tres en raya.

Ejemplo de uso (cada uno en un terminal):

Broker:
    python pubsub_tictactoe.py broker --host 127.0.0.1 --port 9000

Jugador 1 (X):
    python pubsub_tictactoe.py cliente --nombre Alicia --marca X --topic partida1 --host 127.0.0.1 --port 9000

Jugador 2 (O):
    python pubsub_tictactoe.py cliente --nombre Bruno --marca O --topic partida1 --host 127.0.0.1 --port 9000

El cliente se suscribe al topic y publica movimientos; el broker reenvía los mensajes a todos los suscriptores.
"""

import argparse
import queue
import socket
import threading
from typing import Dict, List, Tuple


def recibir_lineas(conexion: socket.socket, evento_parada: threading.Event):
    """Genera líneas completas terminadas en '\n' hasta que se cierra la conexión."""
    almacenamiento = b""
    while not evento_parada.is_set():
        try:
            fragmento = conexion.recv(4096)
        except OSError:
            break
        if not fragmento:
            break
        almacenamiento += fragmento
        while b"\n" in almacenamiento:
            linea, almacenamiento = almacenamiento.split(b"\n", 1)
            yield linea.decode(errors="ignore").strip()


class Broker:
    def __init__(self, host: str, port: int):
        self.host = host
        self.port = port
        self.suscriptores: Dict[str, List[Tuple[socket.socket, threading.Lock]]] = {}
        self.lock = threading.Lock()
        self.evento_parada = threading.Event()

    def iniciar(self):
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as servidor:
            servidor.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
            servidor.bind((self.host, self.port))
            servidor.listen()
            print(f"[broker] escuchando en {self.host}:{self.port}")
            while not self.evento_parada.is_set():
                try:
                    cliente, direccion = servidor.accept()
                except OSError:
                    break
                print(f"[broker] conexión desde {direccion}")
                threading.Thread(target=self.manejar_cliente, args=(cliente,), daemon=True).start()
            print("[broker] finalizando")

    def manejar_cliente(self, conexion: socket.socket):
        lector_parada = threading.Event()
        try:
            for linea in recibir_lineas(conexion, lector_parada):
                if not linea:
                    continue
                partes = linea.split(" ", 2)
                if len(partes) < 2:
                    continue
                comando, topic = partes[0], partes[1]
                if comando == "SUB":
                    self.agregar_suscriptor(topic, conexion)
                    self.enviar_linea(conexion, f"ACK SUB {topic}")
                elif comando == "PUB" and len(partes) == 3:
                    carga = partes[2]
                    self.reenviar(topic, carga, remitente=conexion)
                else:
                    self.enviar_linea(conexion, "ERR no soportado")
        finally:
            lector_parada.set()
            self.quitar_suscriptor(conexion)
            try:
                conexion.close()
            except OSError:
                pass

    def agregar_suscriptor(self, topic: str, conexion: socket.socket):
        with self.lock:
            if topic not in self.suscriptores:
                self.suscriptores[topic] = []
            self.suscriptores[topic].append((conexion, threading.Lock()))
        print(f"[broker] suscrito a {topic}; total {len(self.suscriptores.get(topic, []))}")

    def quitar_suscriptor(self, conexion: socket.socket):
        with self.lock:
            for topic, lista in list(self.suscriptores.items()):
                actualizados = [(sock, candado) for (sock, candado) in lista if sock != conexion]
                if actualizados:
                    self.suscriptores[topic] = actualizados
                else:
                    self.suscriptores.pop(topic, None)
        print("[broker] cliente desconectado")

    def reenviar(self, topic: str, carga: str, remitente: socket.socket):
        with self.lock:
            destinos = list(self.suscriptores.get(topic, []))
        for destino, candado in destinos:
            try:
                with candado:
                    self.enviar_linea(destino, f"MSG {topic} {carga}")
            except OSError:
                pass

    @staticmethod
    def enviar_linea(conexion: socket.socket, texto: str):
        conexion.sendall((texto + "\n").encode())


class TresEnRaya:
    def __init__(self, nombre: str, marca: str, topic: str, host: str, port: int):
        self.nombre = nombre
        self.marca = marca.upper()
        if self.marca not in {"X", "O"}:
            raise ValueError("la marca debe ser X u O")
        self.topic = topic
        self.host = host
        self.port = port
        self.tablero = [[" "] * 3 for _ in range(3)]
        self.conexion = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self.entradas = queue.Queue()
        self.evento_parada = threading.Event()

    def conectar(self):
        self.conexion.connect((self.host, self.port))
        Broker.enviar_linea(self.conexion, f"SUB {self.topic}")
        threading.Thread(target=self.lector, daemon=True).start()
        threading.Thread(target=self.consumidor, daemon=True).start()
        print(f"[cliente] conectado al broker {self.host}:{self.port} en topic {self.topic}")

    def lector(self):
        for linea in recibir_lineas(self.conexion, self.evento_parada):
            if linea:
                self.entradas.put(linea)
        self.evento_parada.set()

    def consumidor(self):
        while not self.evento_parada.is_set():
            try:
                linea = self.entradas.get(timeout=0.2)
            except queue.Empty:
                continue
            if linea.startswith("MSG "):
                self.manejar_mensaje(linea)
            elif linea.startswith("ACK"):
                print(f"[cliente] broker: {linea}")
            else:
                print(f"[cliente] broker: {linea}")

    def manejar_mensaje(self, linea: str):
        partes = linea.split(" ", 2)
        if len(partes) != 3:
            return
        carga = partes[2]
        if carga.startswith("MOVE"):
            _, fila, columna, marca = carga.split()
            self.aplicar_movimiento(int(fila), int(columna), marca)
        elif carga.startswith("TEXT"):
            print(carga[5:])

    def aplicar_movimiento(self, fila: int, columna: int, marca: str):
        if 0 <= fila < 3 and 0 <= columna < 3 and self.tablero[fila][columna] == " ":
            self.tablero[fila][columna] = marca
            print(f"[cliente] movimiento {marca} en ({fila},{columna})")
            self.imprimir_tablero()
            ganador = self.verificar_ganador()
            if ganador:
                print(f"[cliente] ganador: {ganador}")
            elif self.es_empate():
                print("[cliente] empate")

    def publicar_movimiento(self, fila: int, columna: int):
        carga = f"MOVE {fila} {columna} {self.marca}"
        Broker.enviar_linea(self.conexion, f"PUB {self.topic} {carga}")

    def publicar_texto(self, texto: str):
        Broker.enviar_linea(self.conexion, f"PUB {self.topic} TEXT {self.nombre}: {texto}")

    def imprimir_tablero(self):
        print("\n".join([" | ".join(fila) for fila in self.tablero]))
        print("-----")

    def verificar_ganador(self):
        lineas = []
        lineas.extend(self.tablero)
        lineas.extend([[self.tablero[fila][columna] for fila in range(3)] for columna in range(3)])
        lineas.append([self.tablero[i][i] for i in range(3)])
        lineas.append([self.tablero[i][2 - i] for i in range(3)])
        for linea in lineas:
            if linea[0] != " " and linea.count(linea[0]) == 3:
                return linea[0]
        return None

    def es_empate(self):
        return all(celda != " " for fila in self.tablero for celda in fila)

    def bucle(self):
        print("Escribe: fila columna (ej. 0 2) o /quit")
        while not self.evento_parada.is_set():
            try:
                entrada = input("> ").strip()
            except (EOFError, KeyboardInterrupt):
                break
            if entrada in {"/quit", "quit", "exit"}:
                break
            if entrada.startswith("say "):
                self.publicar_texto(entrada[4:])
                continue
            partes = entrada.split()
            if len(partes) != 2:
                print("introduce fila y columna")
                continue
            try:
                fila, columna = int(partes[0]), int(partes[1])
            except ValueError:
                print("no es un número")
                continue
            self.publicar_movimiento(fila, columna)
        self.evento_parada.set()
        try:
            self.conexion.close()
        except OSError:
            pass


def obtener_argumentos():
    parser = argparse.ArgumentParser(description="Socket pub/sub tres en raya")
    subparsers = parser.add_subparsers(dest="rol", required=True)

    broker_parser = subparsers.add_parser("broker", help="Ejecuta el broker")
    broker_parser.add_argument("--host", default="127.0.0.1")
    broker_parser.add_argument("--port", type=int, default=9000)

    cliente_parser = subparsers.add_parser("cliente", help="Ejecuta un cliente")
    cliente_parser.add_argument("--host", default="127.0.0.1")
    cliente_parser.add_argument("--port", type=int, default=9000)
    cliente_parser.add_argument("--nombre", required=True)
    cliente_parser.add_argument("--marca", choices=["X", "O", "x", "o"], required=True)
    cliente_parser.add_argument("--topic", default="partida1")

    return parser.parse_args()


def main():
    args = obtener_argumentos()
    if args.rol == "broker":
        Broker(args.host, args.port).iniciar()
    else:
        cliente = TresEnRaya(args.nombre, args.marca, args.topic, args.host, args.port)
        cliente.conectar()
        cliente.bucle()


if __name__ == "__main__":
    main()
