import { useEffect, useState, type ReactNode } from "react";
import { api } from "../api/client";
import { gateFor, type Gate } from "../lib/login";
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

  if (gate === "checking") return null; // one quick request; avoids flashing the login
  if (gate === "login") return <LoginPage onLogin={() => setGate("open")} />;
  return <>{children}</>;
}
