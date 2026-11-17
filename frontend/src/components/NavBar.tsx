import { isDemo } from "../api/client";
import type { Theme } from "../lib/theme";
import { UploadButton } from "./UploadButton";

interface Props {
  onFiles: (files: File[]) => void;
  theme: Theme;
  onToggleTheme: () => void;
  sidebarOpen?: boolean; // undefined: no sidebar to toggle (empty state)
  onToggleSidebar?: () => void;
}

export function NavBar(props: Props) {
  const { onFiles, theme, onToggleTheme, sidebarOpen, onToggleSidebar } = props;
  const next = theme === "dark" ? "light" : "dark";
  return (
    <header className="nav-bar">
      {onToggleSidebar && (
        <button
          type="button"
          className="btn btn-bar icon-only"
          onClick={onToggleSidebar}
          aria-expanded={sidebarOpen}
          aria-label={sidebarOpen ? "Hide documents" : "Show documents"}
          title={sidebarOpen ? "Hide documents" : "Show documents"}
        >
          ☰
        </button>
      )}
      <div className="wordmark">
        <span className="wordmark-mark" aria-hidden />
        askBob
      </div>
      <div className="nav-actions">
        <button
          type="button"
          className="btn btn-bar icon-only"
          onClick={onToggleTheme}
          aria-label={`Switch to ${next} mode`}
          title={`Switch to ${next} mode`}
        >
          {theme === "dark" ? "☀" : "☾"}
        </button>
        {isDemo ? (
          // The demo build replays real runs and takes no uploads (D-059).
          <a
            className="btn btn-bar"
            href="https://github.com/slowTake/bobBuilder"
            title="Answers are replayed from real runs. Clone the repo to run it live."
          >
            Recorded demo · run it live
          </a>
        ) : (
          <UploadButton onFiles={onFiles} />
        )}
      </div>
    </header>
  );
}
