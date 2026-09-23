import { useState } from "react";
import { Link, useNavigate } from "react-router-dom";
import { useAuth } from "@/context/AuthContext";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Card } from "@/components/ui/card";
import { toast } from "sonner";
import { formatError } from "@/api";

export default function Register() {
  const { register } = useAuth();
  const nav = useNavigate();
  const [u, setU] = useState("");
  const [p, setP] = useState("");
  const [busy, setBusy] = useState(false);

  const submit = async (e) => {
    e.preventDefault();
    setBusy(true);
    try {
      await register(u, p);
      nav("/");
    } catch (err) {
      toast.error(formatError(err.response?.data?.detail) || err.message);
    } finally {
      setBusy(false);
    }
  };

  return (
    <div className="min-h-screen flex items-center justify-center px-6">
      <Card className="w-full max-w-md bg-bisca-bordeaux border-bisca-gold/20 p-8">
        <h1 className="font-serif text-5xl text-bisca-gold mb-2">Registrati</h1>
        <p className="text-bisca-muted mb-8">Crea un account per salvare le tue statistiche</p>
        <form onSubmit={submit} className="space-y-5">
          <div>
            <Label className="text-bisca-text">Username</Label>
            <Input data-testid="register-username" value={u} onChange={(e) => setU(e.target.value)} className="mt-1 bg-bisca-wood border-bisca-gold/20 text-bisca-text" autoFocus required minLength={3} maxLength={20} />
          </div>
          <div>
            <Label className="text-bisca-text">Password</Label>
            <Input data-testid="register-password" type="password" value={p} onChange={(e) => setP(e.target.value)} className="mt-1 bg-bisca-wood border-bisca-gold/20 text-bisca-text" required minLength={4} />
          </div>
          <Button data-testid="register-submit" disabled={busy} className="w-full bg-bisca-red hover:bg-bisca-red/90 text-white rounded-full">
            {busy ? "…" : "Crea account"}
          </Button>
        </form>
        <p className="text-sm text-bisca-muted mt-6">
          Hai già un account? <Link data-testid="link-login" to="/login" className="text-bisca-gold hover:underline">Accedi</Link>
        </p>
      </Card>
    </div>
  );
}
