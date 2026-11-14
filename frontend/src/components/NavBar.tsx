import type { Theme } from "../lib/theme";
import { ExportMenu, type Exports } from "./ExportMenu";
import { UploadButton } from "./UploadButton";

interface Props {
  onFiles: (files: File[]) => void;
  theme: Theme;
  onToggleTheme: () => void;
  sidebarOpen?: boolean; // undefined: no sidebar to toggle (empty state)
  onToggleSidebar?: () => void;
  /** The Export menu, while the documents panel (which has it too) is hidden. */
  exports?: Exports;
}

export function NavBar(props: Props) {
  const { onFiles, theme, onToggleTheme, sidebarOpen, onToggleSidebar, exports } = props;
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
        bobBuilder
      </div>
      <div className="nav-actions">
        {exports && <ExportMenu exports={exports} variant="bar" />}
        <button
          type="button"
          className="btn btn-bar icon-only"
          onClick={onToggleTheme}
          aria-label={`Switch to ${next} mode`}
          title={`Switch to ${next} mode`}
        >
          {theme === "dark" ? "☀" : "☾"}
        </button>
        <UploadButton onFiles={onFiles} />
      </div>
    </header>
  );
}
