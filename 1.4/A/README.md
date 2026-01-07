# Pub/Sub Tic-Tac-Toe

Demostración ligera de comunicación grupal indirecta con sockets TCP. Un broker pequeño reenvía mensajes publicados a todos los clientes suscritos a un tema. Dos clientes usan el tema para jugar tres en raya.

## Arquitectura
- **Broker**: servidor TCP; mantiene `tema -> [suscriptores]`. Admite líneas `SUB <tema>` y `PUB <tema> <carga>` y reenvía la carga como `MSG <tema> <carga>`. No hay persistencia ni garantías de orden más allá de TCP.
- **Cliente**: se conecta al broker, se suscribe a un tema y publica movimientos/texto. Un hilo escucha `MSG` y actualiza el tablero e imprime chat/ack.
- **Formato del protocolo**: texto UTF-8 delimitado por saltos de línea. Cada comando ocupa una línea. Ejemplo: `PUB partida1 MOVE 0 2 X`.

-## Requisitos
- Python 3.8+
- Sin dependencias externas.

## Ejecución
Abre tres terminales.

1) Broker
```
python pubsub_tictactoe.py broker --host 127.0.0.1 --port 9000
```

2) Player X
```
python pubsub_tictactoe.py client --nombre Alice --marca X --topic game1 --host 127.0.0.1 --port 9000
```

3) Jugador O
```
python pubsub_tictactoe.py client --nombre Bob --marca O --topic game1 --host 127.0.0.1 --port 9000
```

## Cómo jugar
- Al iniciar, cada cliente se suscribe al tema y muestra los ack. del broker.
- Envía un movimiento con `fila columna` (base 0). El cliente publica `MOVE <fila> <columna> <marca>`; el broker lo reenvía y todos los clientes actualizan el tablero.
- Envía chat con `say <mensaje>` (llegará como `TEXT ...`).
- Sal con `/quit`.
- Validación básica: un movimiento solo ocupa celdas vacías. La detección de ganador y empate es local y ocurre tras cada movimiento aplicado. No hay control de turnos; coordina con tu compañero o amplía el protocolo.

## Flujo de mensajes
1. Cliente → Broker: `SUB partida1`
2. Broker → Cliente: `ACK SUB partida1`
3. Cliente → Broker: `PUB partida1 MOVE 1 1 X`
4. Broker → todos los suscriptores: `MSG partida1 MOVE 1 1 X`

## Notas sobre la comunicación
- **Indirecta**: Los jugadores nunca se comunican cara a cara; todo el tráfico pasa por el broker (comunicación de grupo sobre un tema compartido).
- **Entrega**: Se intenta entregar mientras dura la sesión TCP; si un suscriptor se cae, el broker lo elimina.
- **Concurrencia**: Cada conexión y escucha del broker usa un hilo; los envíos se serializan por socket con candados.
- **Formato**: Los saltos de línea evitan lecturas parciales; `recv` acumula hasta encontrar `\n`.

## Extensiones sugeridas
- Añade un mensaje `TURN` para imponer alternancia.
- Mantén historial por tema para que los suscriptores tardíos se pongan al día.
- Cambia TCP por multicast UDP para experimentar con entregas desordenadas o pérdidas.