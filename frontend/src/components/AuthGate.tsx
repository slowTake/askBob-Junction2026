import { useEffect, useState, type ReactNode } from "react";
import { api } from "../api/client";
import { gateFor, LOGGED_OUT_EVENT, type Gate } from "../lib/login";
import { LoginPage } from "./LoginPage";

/** Shows the login page until the server says this browser may use /api (D-048). */
export function AuthGate({ children }: { children: ReactNode }) {
  const [gate, setGate] = useState<Gate>("checking");

  useEffect(() => {
    let live = true;
    api
      .session()
      .then((s) => gateFor(s))
      .catch(() => gateFor(null))
      .then((g) => {
        if (live) setGate(g);
      });
    return () => {
      live = false;
    };
  }, []);

  // A session that ends mid-use (cookie expired, password changed) brings the login back.
  useEffect(() => {
    const toLogin = () => setGate("login");
    window.addEventListener(LOGGED_OUT_EVENT, toLogin);
    return () => window.removeEventListener(LOGGED_OUT_EVENT, toLogin);
  }, []);

  if (gate === "checking") return null; // one quick request; avoids flashing the login
  if (gate === "login") return <LoginPage onLogin={() => setGate("open")} />;
  return <>{children}</>;
}
