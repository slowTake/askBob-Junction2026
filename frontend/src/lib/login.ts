// The login page (D-048). The server checks the password and sets the session cookie;
// nothing secret lives in the browser.

import type { SessionInfo } from "../api/types";

export const TEAM = ["Peter Nurmi", "Cristian Dohanici", "Niklas Raatikainen", "Lucio Surco"];

/** What the app shows before it knows, and once the server has said. */
export type Gate = "checking" | "login" | "open";

/** The gate for a /api/session answer; null means the server could not be asked. */
export function gateFor(session: SessionInfo | null): Gate {
  // Unreachable server: open the app, whose own errors explain it, rather than a login
  // that cannot succeed.
  if (session === null) return "open";
  return session.required && !session.authenticated ? "login" : "open";
}

/** The message under the password field for a failed login's error code. */
export function loginErrorMessage(code: string): string {
  if (code === "wrong_password") return "That password is not right.";
  if (code === "timeout" || code === "network") return "Cannot reach the server. Try again.";
  return "Logging in failed. Try again.";
}
