import type { Theme } from "../lib/theme";
import { UploadButton } from "./UploadButton";

interface Props {
  onFiles: (files: File[]) => void;
  context: string | null; // the open document, shown as a breadcrumb
  theme: Theme;
  onToggleTheme: () => void;
}

export function NavBar({ onFiles, context, theme, onToggleTheme }: Props) {
  const next = theme === "dark" ? "light" : "dark";
  return (
    <header className="nav-bar">
      <div className="wordmark">
        <span className="wordmark-mark" aria-hidden />
        bobBuilder
      </div>
      <div className="crumbs">
        {context && (
          <>
            <span aria-hidden>/</span>
            <b className="mono">{context}</b>
          </>
        )}
      </div>
      <div className="nav-actions">
        <button
          type="button"
          className="btn btn-bar theme-toggle"
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
