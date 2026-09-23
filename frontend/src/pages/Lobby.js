import { useEffect, useState } from "react";
import { useNavigate } from "react-router-dom";
import { useAuth } from "@/context/AuthContext";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Card } from "@/components/ui/card";
import { api, formatError } from "@/api";
import { toast } from "sonner";
import { LogOut, Trophy, Users, Plus, DoorOpen } from "lucide-react";

export default function Lobby() {
  const { user, logout, refreshMe } = useAuth();
  const nav = useNavigate();
  const [code, setCode] = useState("");
  const [board, setBoard] = useState([]);
  const [busy, setBusy] = useState(false);

  useEffect(() => {
    refreshMe();
    api.get("/leaderboard").then((r) => setBoard(r.data)).catch(() => undefined);
  }, []);

  const create = async () => {
    setBusy(true);
    try {
      const { data } = await api.post("/rooms/create");
      nav(`/room/${data.code}`);
    } catch (e) {
      toast.error(formatError(e.response?.data?.detail));
    } finally { setBusy(false); }
  };

  const join = async () => {
    if (!code.trim()) return;
    setBusy(true);
    try {
      const { data } = await api.post(`/rooms/${code.trim().toUpperCase()}/join`);
      nav(`/room/${data.code}`);
    } catch (e) {
      toast.error(formatError(e.response?.data?.detail));
    } finally { setBusy(false); }
  };

  const stats = user?.stats || { games_played: 0, wins: 0, total_points: 0 };

  return (
    <div className="min-h-screen">
      <header className="flex items-center justify-between px-8 py-6 border-b border-bisca-gold/15">
        <div>
          <h1 className="font-serif text-4xl text-bisca-gold leading-none">Bisca</h1>
          <p className="text-bisca-muted text-sm mt-1">Ciao, <span className="text-bisca-text font-medium">{user?.username}</span></p>
        </div>
        <Button data-testid="logout-btn" variant="ghost" className="text-bisca-muted hover:text-bisca-text" onClick={logout}>
          <LogOut className="w-4 h-4 mr-2" /> Esci
        </Button>
      </header>

      <main className="max-w-6xl mx-auto px-8 py-12 grid gap-8 md:grid-cols-3">
        <Card className="p-8 bg-bisca-bordeaux border-bisca-gold/20 md:col-span-2 space-y-8">
          <div>
            <h2 className="font-serif text-3xl text-bisca-gold mb-1">Nuova partita</h2>
            <p className="text-bisca-muted text-sm">Crea una stanza o unisciti con un codice (3&ndash;8 giocatori).</p>
          </div>
          <div className="grid gap-6 sm:grid-cols-2">
            <div className="p-6 rounded-xl bg-bisca-wood border border-bisca-gold/15">
              <div className="flex items-center gap-2 text-bisca-gold mb-3"><Plus className="w-5 h-5" /><span className="font-serif text-xl">Crea stanza</span></div>
              <p className="text-bisca-muted text-sm mb-6">Sarai l'host della nuova partita.</p>
              <Button data-testid="create-room-btn" onClick={create} disabled={busy} className="w-full bg-bisca-red hover:bg-bisca-red/90 text-white rounded-full">Crea</Button>
            </div>
            <div className="p-6 rounded-xl bg-bisca-wood border border-bisca-gold/15">
              <div className="flex items-center gap-2 text-bisca-gold mb-3"><DoorOpen className="w-5 h-5" /><span className="font-serif text-xl">Unisciti</span></div>
              <Input data-testid="join-code-input" value={code} onChange={(e) => setCode(e.target.value.toUpperCase())} placeholder="ABC12" maxLength={5} className="mb-4 bg-bisca-bordeaux border-bisca-gold/20 text-bisca-text tracking-widest text-center font-mono uppercase" />
              <Button data-testid="join-room-btn" onClick={join} disabled={busy || !code} className="w-full bg-bisca-gold hover:bg-bisca-gold/90 text-bisca-wood rounded-full font-semibold">Entra</Button>
            </div>
          </div>
        </Card>

        <Card className="p-8 bg-bisca-bordeaux border-bisca-gold/20">
          <div className="flex items-center gap-2 text-bisca-gold mb-6"><Trophy className="w-5 h-5" /><h2 className="font-serif text-2xl">Le tue statistiche</h2></div>
          <div className="space-y-4 text-bisca-text">
            <StatRow label="Partite giocate" value={stats.games_played} testid="stat-played" />
            <StatRow label="Vittorie" value={stats.wins} testid="stat-wins" />
            <StatRow label="Punti totali (sballi)" value={stats.total_points} testid="stat-points" />
          </div>
          <div className="mt-8 pt-6 border-t border-bisca-gold/15">
            <div className="flex items-center gap-2 text-bisca-gold mb-4"><Users className="w-4 h-4" /><h3 className="font-serif text-lg">Classifica</h3></div>
            <ol className="space-y-2 text-sm">
              {board.slice(0, 5).map((u, i) => (
                <li key={u.id} className="flex justify-between text-bisca-text">
                  <span className="text-bisca-muted">{i + 1}.</span>
                  <span className="flex-1 ml-2">{u.username}</span>
                  <span className="text-bisca-gold">{u.stats?.wins || 0}</span>
                </li>
              ))}
              {board.length === 0 && <li className="text-bisca-muted text-sm">Ancora nessuna partita giocata.</li>}
            </ol>
          </div>
        </Card>
      </main>
    </div>
  );
}

function StatRow({ label, value, testid }) {
  return (
    <div className="flex justify-between items-center">
      <span className="text-bisca-muted">{label}</span>
      <span data-testid={testid} className="font-serif text-2xl text-bisca-gold">{value}</span>
    </div>
  );
}
