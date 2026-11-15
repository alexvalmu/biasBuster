import { useDropzone } from "react-dropzone";
import { UploadArt } from "./Illustrations";

type Props = {
  onFile: (file: File) => void;
  busy: boolean;
  maxMb?: number;
};

export function Dropzone({ onFile, busy, maxMb = 20 }: Props) {
  const { getRootProps, getInputProps, isDragActive, fileRejections } = useDropzone({
    accept: { "application/pdf": [".pdf"] },
    maxFiles: 1,
    maxSize: maxMb * 1024 * 1024,
    disabled: busy,
    onDropAccepted: ([file]) => onFile(file),
  });

  const rejection = fileRejections[0]?.errors[0];

  return (
    <>
      <div {...getRootProps({ className: `drop hover-open${isDragActive ? " active" : ""}` })}>
        <input {...getInputProps()} aria-label="Upload a paper in PDF format" />
        <UploadArt className={isDragActive ? "open" : ""} />
        <div className="drop-body">
          <span className="kicker">{busy ? "Uploading" : "Start here"}</span>
          <div className="drop-title">
            {busy ? (
              <>
                Reading your <em>paper</em>…
              </>
            ) : isDragActive ? (
              <>
                Release to <em>analyze</em>
              </>
            ) : (
              <>
                Drop a PDF, or <em>browse</em>
              </>
            )}
          </div>
          <div className="drop-hint">Up to {maxMb} MB · we keep the file's hash, never the file</div>
        </div>
        {/* Visual only: a click anywhere in the zone opens the file picker. */}
        <span className="btn" aria-hidden>
          {busy ? "Uploading…" : "Choose a PDF"}
        </span>
      </div>
      {rejection && (
        <p className="error" role="alert">
          {rejection.code === "file-too-large"
            ? `That file is larger than ${maxMb} MB.`
            : "Only PDF files are supported."}
        </p>
      )}
    </>
  );
}
