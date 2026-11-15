import { useState, type FormEvent } from "react";
import { api, ApiError } from "../api/client";
import { loginErrorMessage, TEAM } from "../lib/login";

interface Props {
  onLogin: () => void;
}

/** The front door (D-048): logo, name, team and one password field. */
export function LoginPage({ onLogin }: Props) {
  const [password, setPassword] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [checking, setChecking] = useState(false);

  const submit = async (e: FormEvent) => {
    e.preventDefault();
    setChecking(true);
    try {
      await api.login(password);
      onLogin();
    } catch (err) {
      setError(loginErrorMessage(err instanceof ApiError ? err.code : "unknown"));
      setChecking(false);
    }
  };

  return (
    <main className="login">
      <form className="login-card" onSubmit={submit}>
        <div className="login-brand">
          <span className="login-mark" aria-hidden />
          <h1>askBob</h1>
        </div>
        <p className="login-tagline">
          Ask construction drawings questions and get answers you can verify.
        </p>
        <label className="login-label" htmlFor="login-password">
          Password
        </label>
        <input
          id="login-password"
          className="text-input"
          type="password"
          autoComplete="current-password"
          autoFocus
          value={password}
          onChange={(e) => {
            setPassword(e.target.value);
            setError(null);
          }}
          aria-invalid={error !== null}
          aria-describedby={error ? "login-error" : undefined}
        />
        {error && (
          <p id="login-error" className="login-error" role="alert">
            {error}
          </p>
        )}
        <button type="submit" className="btn btn-primary" disabled={!password || checking}>
          Log in
        </button>
        <footer className="login-team">
          <span>Made by</span>
          <ul>
            {TEAM.map((name) => (
              <li key={name}>{name}</li>
            ))}
          </ul>
        </footer>
      </form>
    </main>
  );
}
