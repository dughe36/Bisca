# Bisca — Multiplayer Web Game

## Original problem statement
Costruire un gioco di carte multiplayer web per la "Bisca" italiana:
- 3-8 giocatori, 40 carte italiane, gerarchia semi denari>coppe>spade>bastoni, valori re>cavallo>fante>7..2>asso.
- Dichiarazione prese a inizio turno (mazziere ultimo con vincolo somma ≠ carte in mano).
- Turni con carte decrescenti; turno finale a 1 carta (vedi carte altrui, non le tue).
- Regola speciale Re di Denari: può essere giocato come nominale o "0 di denari" (tra Re di Coppe e Asso di Denari).
- Eliminazione iterativa: dopo il round da 1 carta si eliminano tutti i pari-merito col punteggio più alto e si itera.

## User choices
- Server-authoritative multiplayer via WebSocket rooms
- Custom account (username + password) con statistiche per utente
- Carte stile Romagnole
- Chat sì, log delle mani no
- Eliminazione: tutti i pari-merito col punteggio più alto vengono eliminati insieme

## Architecture
- Backend: FastAPI + Motor (MongoDB), JWT+bcrypt (cookie httpOnly + Bearer fallback), WebSocket per lo stato di gioco.
- Frontend: React + Tailwind + shadcn/ui, sonner per toast, Cormorant Garamond + Manrope, tema "osteria" bordeaux/oro.
- File chiave:
  - /app/backend/server.py, auth.py, game.py, rooms.py
  - /app/frontend/src/App.js, context/AuthContext.js, api.js
  - /app/frontend/src/pages/{Login,Register,Lobby,RoomPage}.js
  - /app/frontend/src/components/BiscaCard.js (SVG dei 4 semi)

## Implemented (v1 — 2026-02)
- Registrazione / login / logout / me con JWT
- Statistiche utente (games_played, wins, total_points) e leaderboard top-20
- Lobby: crea stanza, entra con codice, stats personali + classifica
- Sala d'attesa 3-8 giocatori con presenza in tempo reale
- Motore Bisca completo:
  - Deal casuale con carte scartate ignote
  - Bidding con vincolo mazziere
  - Trick play con classifica seme×valore
  - Re di Denari con scelta nominale / "0 di denari"
  - Round finale a 1 carta con carte proprie nascoste al viewer
  - Punteggi sballi cumulativi
  - Eliminazione iterativa dei pari-merito
  - Vittoria finale con aggiornamento stats
- Tavolo di gioco con seating ellittico dinamico, dealer/turno evidenziati, chat laterale, scorecard di fine turno

## Backlog (P1 / P2)
- P1: animazioni framer-motion (deal/play/sweep), suoni discreti
- P1: reconnect di partita in corso (attualmente WebSocket-only)
- P1: history dettagliata partite per profilo utente
- P2: spectator mode, ranking ELO, avatar personalizzabili
- P2: partite private con password, kick host, timer per turno
