import { createContext, useContext, useEffect, useState } from "react";
import { api } from "@/api";

const AuthCtx = createContext(null);

export function AuthProvider({ children }) {
  const [user, setUser] = useState(null); // null=loading, false=anon, obj=logged
  useEffect(() => {
    api
      .get("/auth/me")
      .then((r) => setUser(r.data))
      .catch(() => setUser(false));
  }, []);

  const login = async (username, password) => {
    const { data } = await api.post("/auth/login", { username, password });
    if (data.token) localStorage.setItem("bisca_token", data.token);
    setUser(data.user);
    return data.user;
  };
  const register = async (username, password) => {
    const { data } = await api.post("/auth/register", { username, password });
    if (data.token) localStorage.setItem("bisca_token", data.token);
    setUser(data.user);
    return data.user;
  };
  const logout = async () => {
    try { await api.post("/auth/logout"); } catch (e) { /* ignore */ }
    localStorage.removeItem("bisca_token");
    setUser(false);
  };
  const refreshMe = async () => {
    try {
      const r = await api.get("/auth/me");
      setUser(r.data);
    } catch (e) { /* ignore */ }
  };

  return <AuthCtx.Provider value={{ user, login, register, logout, refreshMe }}>{children}</AuthCtx.Provider>;
}

export const useAuth = () => useContext(AuthCtx);
