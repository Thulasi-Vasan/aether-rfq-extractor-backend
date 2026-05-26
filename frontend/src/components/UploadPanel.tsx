import { CheckCircle2, FileText, Loader2, Upload, Workflow } from "lucide-react";
import type React from "react";
import { formatFileSize } from "../lib/format";

interface UploadPanelProps {
  pdfFile: File | null;
  stepFile: File | null;
  loading: boolean;
  error: string | null;
  onPdfChange: (file: File | null) => void;
  onStepChange: (file: File | null) => void;
  onSubmit: () => void;
}

export function UploadPanel({
  pdfFile,
  stepFile,
  loading,
  error,
  onPdfChange,
  onStepChange,
  onSubmit,
}: UploadPanelProps) {
  const canSubmit = Boolean(pdfFile && stepFile && !loading);

  return (
    <aside className="side-panel upload-panel">
      <div className="panel-heading">
        <div>
          <p className="eyebrow">Upload & files</p>
          <h1>Source documents</h1>
        </div>
        <Upload size={18} />
      </div>

      <FilePicker
        icon={<FileText size={18} />}
        label="2D drawing PDF"
        accept=".pdf,application/pdf"
        file={pdfFile}
        onChange={onPdfChange}
      />

      <FilePicker
        icon={<Workflow size={18} />}
        label="STEP model"
        accept=".stp,.step"
        file={stepFile}
        onChange={onStepChange}
      />

      <button className="primary-action" disabled={!canSubmit} onClick={onSubmit}>
        {loading ? <Loader2 className="spin" size={18} /> : <Upload size={18} />}
        Extract details
      </button>

      {error ? <div className="error-box">{error}</div> : null}

      <div className="workflow-box">
        <div>
          <strong>1</strong>
          <span>Upload PDF drawing</span>
        </div>
        <div>
          <strong>2</strong>
          <span>Upload STEP model</span>
        </div>
        <div>
          <strong>3</strong>
          <span>Review extracted values</span>
        </div>
      </div>
    </aside>
  );
}

interface FilePickerProps {
  icon: React.ReactNode;
  label: string;
  accept: string;
  file: File | null;
  onChange: (file: File | null) => void;
}

function FilePicker({ icon, label, accept, file, onChange }: FilePickerProps) {
  return (
    <label className="file-picker">
      <span className="file-label">
        {icon}
        {label}
      </span>
      <input
        type="file"
        accept={accept}
        onChange={(event) => onChange(event.target.files?.[0] ?? null)}
      />
      <span className={`file-value ${file ? "loaded" : ""}`}>
        {file ? (
          <>
            <span className="file-chip">
              <CheckCircle2 size={15} />
              Loaded
            </span>
            <strong>{file.name}</strong>
            <small>{formatFileSize(file.size)}</small>
          </>
        ) : (
          <>
            <strong>Drop or browse</strong>
            <small>Click to choose file</small>
          </>
        )}
      </span>
    </label>
  );
}
