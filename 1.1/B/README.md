# Loteria distribuïda (Activitat 1.B)

Simulació mínima, només amb UDP, d'una loteria distribuïda amb tres tipus d'agents:

- Entitat de Sorteig (DE): realitza sortejos i en difon el resultat per multicast.
- Servidors d'Administració de Loteria (LAS): venen butlletes per unicast i notifiquen guanyadors.
- Clients: compren butlletes a un LAS aleatori i escolten confirmacions i premis.

Decisions clau:
- UDP multicast (224.0.0.1:56000) per anunciar resultats (DE → tots els LAS i clients).
- UDP unicast per a compres/confirmacions (client↔LAS) i avisos de premi (LAS→client).
- Consistència: un únic DE emet el draw_id i el número guanyador; cada LAS comprova les seves butlletes locals i notifica.
- Aleatorietat: el DE usa `secrets.SystemRandom` de Python.

## Execució

Ordre en PowerShell (Windows):

```powershell
python .\1.1\B\main.py --draws 5 --las 2 --clients 5 --period 5
```

Durant l'execució, mireu la consola o el fitxer `loteria_distribuida.log` per als detalls. L'aplicació s'atura sola després del nombre de sortejos indicat.

Si el multicast està bloquejat a l'adaptador de xarxa, executeu-ho tot a la mateixa màquina (per defecte). Si persisteixen problemes, permeteu al tallafoc de Windows que Python rebi UDP multicast pel port 56000.

## Tipus de missatges
- DRAW_RESULT (multicast): { draw_id, winning_number, max_number }
- BUY_TICKET (client→LAS): { client_id, reply_port, current_draw_id, number }
- TICKET_CONFIRMED (LAS→client)
- WINNER_NOTIFICATION (LAS→client)

## Notes
- Ports: els LAS comencen a 56100 (un per LAS) i els clients a 56200 (un per client).
- Un fil seguidor manté el `draw_id` vigent escoltant el multicast perquè els clients comprin sempre pel sorteig actual.
- És una simulació docent: sense persistència ni garanties de reintent/ordenació (propis d'UDP).
