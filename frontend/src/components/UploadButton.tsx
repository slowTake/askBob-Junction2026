import { useRef } from "react";

export const ACCEPTED = ".ifc,.pdf,.png,.jpg,.jpeg,.tif,.tiff";

interface Props {
  onFiles: (files: File[]) => void;
  label?: string;
  variant?: "primary" | "secondary";
}

export function UploadButton({ onFiles, label = "Upload drawing", variant = "primary" }: Props) {
  const input = useRef<HTMLInputElement>(null);
  return (
    <>
      <button type="button" className={`btn btn-${variant}`} onClick={() => input.current?.click()}>
        {label}
      </button>
      <input
        ref={input}
        type="file"
        accept={ACCEPTED}
        multiple
        hidden
        onChange={(e) => {
          onFiles(Array.from(e.target.files ?? []));
          e.target.value = "";
        }}
      />
    </>
  );
}
