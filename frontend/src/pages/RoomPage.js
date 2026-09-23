import { useEffect, useRef, useState, useCallback } from "react";
import { useParams, useNavigate } from "react-router-dom";
import { useAuth } from "@/context/AuthContext";
import { BACKEND_URL, api } from "@/api";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Card } from "@/components/ui/card";
import { Dialog, DialogContent, DialogHeader, DialogTitle, DialogDescription, DialogFooter } from "@/components/ui/dialog";
import BiscaCard from "@/components/BiscaCard";
import { toast } from "sonner";
import { Send, LogOut, Copy, Play, Crown, MessageSquare } from "lucide-react";

export default function RoomPage() {
  const { code } = useParams();
  const { user } = useAuth();
  const nav = useNavigate();
  const wsRef = useRef(null);
  const [state, setState] = useState(null);
  const [chatText, setChatText] = useState("");
  const [showChat, setShowChat] = useState(false);
  const [connected, setConnected] = useState(false);

  const send = useCallback((msg) => {
    if (wsRef.current && wsRef.current.readyState === 1) wsRef.current.send(JSON.stringify(msg));
  }, []);

  useEffect(() => {
    let cancelled = false;
    const token = localStorage.getItem("bisca_token");
    const wsUrl = BACKEND_URL.replace(/^http/, "ws") + `/api/ws/${code}?token=${encodeURIComponent(token || "")}`;
    const ws = new WebSocket(wsUrl);
    wsRef.current = ws;
    ws.onopen = () => setConnected(true);
    ws.onmessage = (ev) => {
      try {
        const msg = JSON.parse(ev.data);
        if (msg.type === "state") setState(msg.state);
        else if (msg.type === "error") toast.error(msg.message);
      } catch (e) { /* ignore */ }
    };
    ws.onclose = () => setConnected(false);
    ws.onerror = () => setConnected(false);
    return () => { cancelled = true; ws.close(); };
  }, [code]);

  // auto-continue after trick reveal
  useEffect(() => {
    if (state?.game?.phase === "trick_reveal") {
      const t = setTimeout(() => send({ type: "continue_trick" }), 1800);
      return () => clearTimeout(t);
    }
  }, [state?.game?.phase, send]);

  if (!state) return <div className="min-h-screen flex items-center justify-center text-bisca-text">Connessione alla stanza…</div>;

  const iAmHost = state.host_id === user.id;
  const game = state.game;

  return (
    <div className="min-h-screen flex flex-col">
      <header className="flex items-center justify-between px-6 py-4 border-b border-bisca-gold/15">
        <div className="flex items-center gap-4">
          <h1 className="font-serif text-2xl text-bisca-gold">Bisca</h1>
          <div className="flex items-center gap-2 text-sm">
            <span className="text-bisca-muted">Codice:</span>
            <span data-testid="room-code" className="font-mono tracking-widest text-bisca-text bg-bisca-wood px-3 py-1 rounded border border-bisca-gold/20">{state.code}</span>
            <Button size="icon" variant="ghost" onClick={() => { navigator.clipboard.writeText(state.code); toast.success("Codice copiato"); }} className="text-bisca-muted hover:text-bisca-gold h-8 w-8">
              <Copy className="w-4 h-4" />
            </Button>
          </div>
          <span className={`text-xs px-2 py-1 rounded ${connected ? "bg-bisca-green/30 text-bisca-parchment" : "bg-bisca-red/30 text-bisca-parchment"}`}>{connected ? "Connesso" : "…"}</span>
        </div>
        <div className="flex items-center gap-2">
          <Button variant="ghost" size="icon" onClick={() => setShowChat((v) => !v)} data-testid="toggle-chat" className="text-bisca-muted hover:text-bisca-gold">
            <MessageSquare className="w-5 h-5" />
          </Button>
          <Button data-testid="leave-room-btn" variant="ghost" onClick={() => { send({ type: "leave" }); nav("/"); }} className="text-bisca-muted hover:text-bisca-text">
            <LogOut className="w-4 h-4 mr-2" /> Esci
          </Button>
        </div>
      </header>

      <div className="flex-1 relative">
        {state.status === "waiting" && <WaitingRoom state={state} iAmHost={iAmHost} onStart={() => send({ type: "start_game" })} />}
        {state.status === "playing" && game && <GameTable state={state} game={game} me={user} send={send} />}
        {state.status === "finished" && game && <FinishedView state={state} game={game} me={user} />}
        {showChat && <ChatPanel state={state} me={user} onSend={(t) => send({ type: "chat", text: t })} chatText={chatText} setChatText={setChatText} onClose={() => setShowChat(false)} />}
      </div>
    </div>
  );
}

function WaitingRoom({ state, iAmHost, onStart }) {
  return (
    <div className="max-w-3xl mx-auto p-10">
      <Card className="p-8 bg-bisca-bordeaux border-bisca-gold/20">
        <h2 className="font-serif text-3xl text-bisca-gold mb-2">Sala d&apos;attesa</h2>
        <p className="text-bisca-muted mb-6">In attesa dei giocatori… servono da 3 a 8 partecipanti.</p>
        <div className="space-y-3 mb-8">
          {state.players.map((p) => (
            <div key={p.user_id} className="flex items-center justify-between p-4 rounded-lg bg-bisca-wood border border-bisca-gold/10">
              <div className="flex items-center gap-3">
                <div className="w-10 h-10 rounded-full bg-bisca-gold/20 flex items-center justify-center font-serif text-bisca-gold">{p.username[0]?.toUpperCase()}</div>
                <span className="text-bisca-text">{p.username}</span>
                {p.user_id === state.host_id && <Crown className="w-4 h-4 text-bisca-gold" />}
              </div>
              <span className={`text-xs px-2 py-0.5 rounded ${p.connected ? "bg-bisca-green/30 text-bisca-parchment" : "bg-bisca-red/20 text-bisca-muted"}`}>{p.connected ? "Online" : "Offline"}</span>
            </div>
          ))}
        </div>
        {iAmHost && (
          <Button data-testid="start-game-btn" disabled={state.players.length < 3} onClick={onStart} className="w-full bg-bisca-red hover:bg-bisca-red/90 text-white rounded-full">
            <Play className="w-4 h-4 mr-2" /> Inizia partita
          </Button>
        )}
        {!iAmHost && <p className="text-center text-bisca-muted text-sm">L&apos;host può iniziare la partita quando siete pronti.</p>}
      </Card>
    </div>
  );
}

function GameTable({ state, game, me, send }) {
  const players = state.players.filter((p) => game.player_order.includes(p.user_id));
  const myIdx = game.player_order.indexOf(me.id);
  const myHand = game.hands[me.id] || [];
  const isMyTurnBid = game.phase === "bidding" && game.current_bidder === me.id;
  const isMyTurnPlay = game.phase === "playing" && game.current_player === me.id;
  const pendingRe = game.pending_re_denari && game.pending_re_denari.player_id === me.id;

  // reorder so me at index 0 (bottom center)
  const ordered = myIdx >= 0 ? [...game.player_order.slice(myIdx), ...game.player_order.slice(0, myIdx)] : game.player_order;

  const seatPositions = (n) => {
    // Bottom fixed for local. Others distributed on top/sides.
    const positions = [];
    positions.push({ x: 50, y: 82, self: true });
    if (n === 1) return positions;
    for (let i = 1; i < n; i++) {
      const t = i / n; // 0..1
      const angle = Math.PI * (1.15 - t * 1.3); // from left top to right top
      const x = 50 + 42 * Math.cos(angle);
      const y = 38 - 18 * Math.sin(angle - Math.PI / 2);
      positions.push({ x, y, self: false });
    }
    return positions;
  };
  const positions = seatPositions(ordered.length);

  const activeId = game.current_player || game.current_bidder;

  return (
    <div className="relative w-full h-[calc(100vh-72px)] overflow-hidden">
      {/* Center trick area */}
      <div className="absolute left-1/2 top-1/2 -translate-x-1/2 -translate-y-1/2 flex flex-col items-center gap-4">
        <div className="text-center">
          <div className="text-bisca-muted text-xs">Turno {game.round_number} · {game.cards_per_hand} carte {game.is_final_round && "(finale)"}</div>
          <div className="font-serif text-2xl text-bisca-gold mt-1">
            {game.phase === "bidding" && "Dichiarazioni in corso"}
            {game.phase === "playing" && "Gioca una carta"}
            {game.phase === "trick_reveal" && "Presa!"}
            {game.phase === "round_end" && "Fine turno"}
          </div>
        </div>
        <div className="flex gap-2 items-center min-h-[6rem]">
          {game.current_trick.map((t) => {
            const pl = players.find((p) => p.user_id === t.player_id);
            return (
              <div key={t.player_id} className="flex flex-col items-center gap-1">
                <BiscaCard card={t.card} data-testid={`trick-card-${t.player_id}`} />
                <span className="text-xs text-bisca-muted">{pl?.username}{t.re_denari_as_zero && " (0 di denari)"}</span>
              </div>
            );
          })}
        </div>
      </div>

      {/* Player seats */}
      {ordered.map((pid, i) => {
        const p = players.find((x) => x.user_id === pid);
        if (!p) return null;
        const pos = positions[i];
        const isSelf = pos.self;
        const isDealer = game.dealer_id === pid;
        const isActive = activeId === pid;
        const bid = game.bids[pid];
        const tricks = game.tricks_won[pid] || 0;
        const isEliminated = game.eliminated.includes(pid);
        return (
          <div key={pid} className="absolute -translate-x-1/2 -translate-y-1/2 flex flex-col items-center gap-2" style={{ left: `${pos.x}%`, top: `${pos.y}%`, opacity: isEliminated ? 0.4 : 1 }}>
            <div data-testid={`seat-${pid}`} className={`px-3 py-2 rounded-lg bg-bisca-bordeaux/90 border ${isActive ? "border-bisca-gold glow-active" : "border-bisca-gold/20"} min-w-[10rem] text-center`}>
              <div className="flex items-center justify-center gap-1 text-bisca-text font-medium">
                {isDealer && <Crown className="w-3 h-3 text-bisca-gold" />}
                <span className="truncate max-w-[7rem]">{p.username}</span>
                {isEliminated && <span className="text-xs text-bisca-red">✕</span>}
              </div>
              <div className="text-xs text-bisca-muted mt-0.5">
                Prese: <span className="text-bisca-gold">{tricks}</span>
                {bid !== null && bid !== undefined && <> / dich. <span className="text-bisca-parchment">{bid}</span></>}
              </div>
              <div className="text-xs text-bisca-muted">Sballi: <span className="text-bisca-red">{game.scores[pid] || 0}</span></div>
            </div>
            {!isSelf && (
              <div className="flex gap-0.5">
                {(game.hands[pid] || []).map((c, ci) => (
                  <BiscaCard key={ci} card={c} hidden={c.hidden && !game.is_final_round} faceDown={c.hidden && !game.is_final_round} small />
                ))}
              </div>
            )}
          </div>
        );
      })}

      {/* My hand */}
      <div className="absolute left-1/2 bottom-4 -translate-x-1/2 flex gap-2 items-end" data-testid="my-hand">
        {myHand.map((c, i) => {
          const canPlay = isMyTurnPlay && !c.hidden;
          const hiddenSelf = c.hidden && game.is_final_round;
          return (
            <BiscaCard
              key={c.id || i}
              card={c}
              hidden={hiddenSelf}
              faceDown={hiddenSelf}
              onClick={canPlay ? () => send({ type: "play_card", card_id: c.id }) : (hiddenSelf && isMyTurnPlay ? () => send({ type: "play_card", card_id: c.id }) : undefined)}
              playable={canPlay}
              data-testid={`my-card-${c.id || i}`}
            />
          );
        })}
      </div>

      {/* Bidding controls */}
      {isMyTurnBid && <BiddingBar game={game} me={me} send={send} />}

      {/* Re di Denari modal */}
      <Dialog open={!!pendingRe}>
        <DialogContent className="bg-bisca-bordeaux border-bisca-gold/40 text-bisca-text">
          <DialogHeader>
            <DialogTitle className="font-serif text-3xl text-bisca-gold">Re di Denari</DialogTitle>
            <DialogDescription className="text-bisca-muted">Come vuoi giocare questa carta?</DialogDescription>
          </DialogHeader>
          <div className="flex gap-4 justify-center py-4">
            <BiscaCard card={{ suit: "denari", value: 10, id: "denari-10" }} />
          </div>
          <DialogFooter className="gap-2 sm:justify-center">
            <Button data-testid="re-denari-nominal" onClick={() => send({ type: "re_denari_choice", as_zero: false })} className="bg-bisca-gold text-bisca-wood hover:bg-bisca-gold/90 rounded-full">Valore nominale (massimo)</Button>
            <Button data-testid="re-denari-zero" onClick={() => send({ type: "re_denari_choice", as_zero: true })} variant="outline" className="border-bisca-gold text-bisca-gold hover:bg-bisca-gold/10 rounded-full">0 di denari</Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>

      {/* Round end */}
      {game.phase === "round_end" && (
        <div className="absolute inset-0 bg-bisca-wood/80 backdrop-blur-sm flex items-center justify-center">
          <Card className="p-8 bg-bisca-bordeaux border-bisca-gold/30 max-w-lg">
            <h2 className="font-serif text-3xl text-bisca-gold mb-4">Fine turno</h2>
            <table className="w-full text-sm mb-6">
              <thead><tr className="text-bisca-muted"><th className="text-left">Giocatore</th><th>Dich.</th><th>Prese</th><th>Sballi</th></tr></thead>
              <tbody>
                {game.player_order.map((pid) => {
                  const p = players.find((x) => x.user_id === pid);
                  const elim = game.eliminated.includes(pid);
                  return (
                    <tr key={pid} className={`text-bisca-text ${elim ? "opacity-40 line-through" : ""}`}>
                      <td className="py-1">{p?.username}</td>
                      <td className="text-center">{game.bids[pid] ?? "-"}</td>
                      <td className="text-center">{game.tricks_won[pid] ?? "-"}</td>
                      <td className="text-center text-bisca-red font-semibold">{game.scores[pid] || 0}</td>
                    </tr>
                  );
                })}
              </tbody>
            </table>
            {state.host_id === me.id ? (
              <Button data-testid="next-round-btn" onClick={() => send({ type: "next_round" })} className="w-full bg-bisca-red hover:bg-bisca-red/90 text-white rounded-full">Turno successivo</Button>
            ) : (
              <p className="text-center text-bisca-muted text-sm">In attesa che l&apos;host inizi il turno successivo…</p>
            )}
          </Card>
        </div>
      )}
    </div>
  );
}

function BiddingBar({ game, me, send }) {
  const max = game.cards_per_hand;
  const isDealer = game.dealer_id === me.id;
  const otherSum = Object.entries(game.bids).reduce((s, [pid, v]) => (pid === me.id ? s : s + (v || 0)), 0);
  const forbidden = isDealer ? max - otherSum : null;
  return (
    <div className="absolute left-1/2 bottom-32 -translate-x-1/2 flex flex-wrap gap-2 justify-center bg-bisca-bordeaux/95 border border-bisca-gold/30 backdrop-blur-md rounded-full px-4 py-3">
      <span className="text-bisca-muted text-sm self-center mr-2">Dichiara le tue prese:</span>
      {Array.from({ length: max + 1 }, (_, i) => {
        const forb = isDealer && i === forbidden;
        return (
          <Button
            key={i}
            data-testid={`bid-${i}`}
            disabled={forb}
            onClick={() => send({ type: "bid", bid: i })}
            className={`rounded-full h-10 w-10 p-0 font-serif text-lg ${forb ? "bg-bisca-red/20 text-bisca-red line-through" : "bg-bisca-gold text-bisca-wood hover:bg-bisca-gold/90"}`}
            title={forb ? "Il mazziere non può dichiarare questo numero" : ""}
          >{i}</Button>
        );
      })}
    </div>
  );
}

function ChatPanel({ state, me, onSend, chatText, setChatText, onClose }) {
  return (
    <div className="absolute right-4 top-4 bottom-4 w-80 bg-bisca-bordeaux/95 backdrop-blur-md border border-bisca-gold/25 rounded-xl flex flex-col z-20">
      <div className="p-4 border-b border-bisca-gold/15 flex justify-between items-center">
        <h3 className="font-serif text-xl text-bisca-gold">Chat</h3>
        <Button variant="ghost" size="sm" className="text-bisca-muted" onClick={onClose}>×</Button>
      </div>
      <div className="flex-1 overflow-y-auto p-4 space-y-2 text-sm">
        {(state.chat || []).map((m, i) => (
          <div key={i} className={m.user_id === me.id ? "text-right" : ""}>
            <span className="text-bisca-gold text-xs mr-1">{m.username}</span>
            <div className={`inline-block px-3 py-1.5 rounded-lg ${m.user_id === me.id ? "bg-bisca-red/40" : "bg-bisca-wood"} text-bisca-text`}>{m.text}</div>
          </div>
        ))}
      </div>
      <form className="p-3 border-t border-bisca-gold/15 flex gap-2" onSubmit={(e) => { e.preventDefault(); if (chatText.trim()) { onSend(chatText); setChatText(""); } }}>
        <Input data-testid="chat-input" value={chatText} onChange={(e) => setChatText(e.target.value)} placeholder="Scrivi…" className="bg-bisca-wood border-bisca-gold/20 text-bisca-text" />
        <Button data-testid="chat-send" type="submit" size="icon" className="bg-bisca-gold text-bisca-wood hover:bg-bisca-gold/90"><Send className="w-4 h-4" /></Button>
      </form>
    </div>
  );
}

function FinishedView({ state, game, me }) {
  const winner = state.players.find((p) => p.user_id === game.winner);
  return (
    <div className="max-w-2xl mx-auto p-10">
      <Card className="p-10 bg-bisca-bordeaux border-bisca-gold/30 text-center">
        <Crown className="w-16 h-16 text-bisca-gold mx-auto mb-4" />
        <h2 className="font-serif text-4xl text-bisca-gold mb-2">Vincitore!</h2>
        <p data-testid="winner-name" className="text-2xl text-bisca-text mb-8">{winner?.username || "—"}</p>
        <table className="w-full text-sm mb-6">
          <thead><tr className="text-bisca-muted"><th className="text-left">Giocatore</th><th>Sballi totali</th></tr></thead>
          <tbody>
            {state.players.map((p) => (
              <tr key={p.user_id} className="text-bisca-text">
                <td className="py-1">{p.username}</td>
                <td className="text-center text-bisca-red">{game.scores[p.user_id] || 0}</td>
              </tr>
            ))}
          </tbody>
        </table>
        <Button onClick={() => (window.location.href = "/")} className="bg-bisca-red hover:bg-bisca-red/90 text-white rounded-full">Torna alla lobby</Button>
      </Card>
    </div>
  );
}
