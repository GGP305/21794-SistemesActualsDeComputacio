# Comunicació d'agents amb UDP (Activitat 1.A)

Simulació mínima de comunicació asíncrona entre agents mitjançant sockets UDP i multicast.

Hi participen dos tipus d'agents:
- Sol·licitant: emet peticions d'ajuda al grup multicast i comprova si s'assoleix un quòrum d'ajudes.
- Ajudants: escolten peticions i responen segons probabilitats (ajudar, denegar o no respondre).

Decisions clau:
- Un únic grup UDP multicast 224.0.0.1:5000 per a totes les trames (peticions i respostes).
- Missatges en format JSON amb camps comuns i `request_id` per correlacionar respostes.
- Quòrum: el sol·licitant considera la petició satisfeta quan rep ≥ 2 respostes d'ajuda (HELP_OK) per al mateix `request_id`.
- Temporització: els ajudants responen després d'un retard aleatori; el sol·licitant verifica l'estat 5s després de cada petició.

## Execució

PowerShell (Windows):

```powershell
# Amb el Python del sistema
python .\1.1\A\main.py
```

Durant l'execució, consulteu la consola o el fitxer de log `comunicacio_agents.log` per veure els detalls. L'aplicació llança 1 sol·licitant i 3 ajudants, i finalitza en acabar el cicle de peticions.

> Nota: si al directori veieu un fitxer antic `agent_communication.log`, correspon a una versió anterior. El codi actual escriu al fitxer `comunicacio_agents.log`.

## Tipus de missatges

- HELP_REQUEST: petició d'ajuda (Sol·licitant → grup)
- HELP_OK: ajuda acceptada (Ajudant → grup)
- HELP_NO: ajuda denegada (Ajudant → grup)

Tots els missatges tenen el format JSON següent:

```json
{
  "sender": "Agent-<id>",
  "type": "HELP_REQUEST | HELP_OK | HELP_NO",
  "content": "text lliure",
  "timestamp": "ISO-8601",
  "request_id": 1
}
```

Exemples:
- HELP_REQUEST: `{ "type": "HELP_REQUEST", "content": "#NecessitoAjuda!", "request_id": 3 }`
- HELP_OK: `{ "type": "HELP_OK", "content": "Dacord_3!", "request_id": 3 }`
- HELP_NO: `{ "type": "HELP_NO", "content": "No_3!", "request_id": 3 }`

## Com funciona

- El Sol·licitant incrementa `request_id` i envia `HELP_REQUEST` per multicast cada 3–8 segons.
- Després programa una comprovació per a aquell `request_id` 5s més tard; si ha rebut ≥ 2 `HELP_OK`, marca la petició com a satisfeta.
- Cada Ajudant, en rebre una `HELP_REQUEST`, espera un temps aleatori (0.5–3.0s) i fa una de les accions:
  - 40%: envia `HELP_OK`
  - 50%: envia `HELP_NO`
  - 10%: no respon
- Les respostes també es difonen per multicast i el Sol·licitant les correlaciona pel `request_id`.

## Configuració principal (constants)

Al fitxer `main.py`:
- Grup multicast: `MULTICAST_GROUP = '224.0.0.1'`
- Port base: `BASE_PORT = 5000`
- Mida del buffer: `BUFFER_SIZE = 1024`
- TTL multicast per a l'enviament: 2 salts

Pots modificar aquests valors si cal adaptar-los al teu entorn.

## Requisits

- Python 3.x (només llibreries estàndard: `socket`, `threading`, `json`, `logging`, ...)
- Permisos de xarxa per rebre UDP multicast al port 5000

## Resolució de problemes

- Firewall de Windows: permet que Python rebi trànsit UDP entrant al port 5000 i multicast a l'adreça 224.0.0.1.
- Múltiples interfícies de xarxa: si tens diversos adaptadors (VPN, VirtualBox, etc.) i no reps multicast, prova de desactivar-los temporalment o d'executar-ho tot a la mateixa màquina. En entorns avançats, pot ser necessari especificar la interfície de multicast.
- Port en ús: si un altre procés fa servir el port 5000, ajusta `BASE_PORT` a `main.py` i torna a executar.

## Estructura del codi

- `CommunicationAgent`: classe base amb sockets UDP per rebre (subscripció a multicast) i enviar (multicast TTL=2) i gestió de cicle de vida.
- `RequestingAgent`: emet peticions periòdiques, correlaciona respostes per `request_id`, calcula estadístiques i quòrum (≥ 2 ajudes).
- `HelperAgent`: escolta peticions i decideix si ajuda, denega o ignora, amb un retard aleatori.

## Logs i sortida

- Fitxer: `comunicacio_agents.log` (nivell INFO)
- Consola: missatges resum i estat d'execució

Al final s'imprimeixen estadístiques de satisfacció del quòrum (total de peticions, satisfetes i percentatge).

---

Material docent per a la pràctica de Sistemes Distribuïts: comunicació de grup amb UDP multicast.
