import { UploadButton } from "./UploadButton";

interface Props {
  onFiles: (files: File[]) => void;
}

export function NavBar({ onFiles }: Props) {
  return (
    <header className="nav-bar">
      <div className="wordmark">
        bobBuilder
        <span className="wordmark-sub">Answers you can check on the drawing</span>
      </div>
      <UploadButton onFiles={onFiles} />
    </header>
  );
}
