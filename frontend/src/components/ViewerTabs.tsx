import { Box, FileText } from "lucide-react";
import { resolveApiUrl } from "../lib/api";
import { PdfViewer } from "./PdfViewer";
import { StepViewer } from "./StepViewer";

interface ViewerTabsProps {
  activeTab: "pdf" | "step";
  onTabChange: (tab: "pdf" | "step") => void;
  pdfUrl?: string;
  stepUrl?: string;
  partLabel?: string | null;
}

export function ViewerTabs({
  activeTab,
  onTabChange,
  pdfUrl,
  stepUrl,
  partLabel,
}: ViewerTabsProps) {
  return (
    <main className="viewer-panel">
      <div className="viewer-header">
        <div>
          <p className="eyebrow">Review</p>
          <h2>{partLabel ?? "No extraction loaded"}</h2>
        </div>
        <div className="tab-control">
          <button
            className={activeTab === "pdf" ? "active" : ""}
            onClick={() => onTabChange("pdf")}
            type="button"
          >
            <FileText size={16} />
            PDF
          </button>
          <button
            className={activeTab === "step" ? "active" : ""}
            onClick={() => onTabChange("step")}
            type="button"
          >
            <Box size={16} />
            STEP
          </button>
        </div>
      </div>

      <div className="viewer-stage">
        {!pdfUrl || !stepUrl ? (
          <div className="empty-viewer">
            Upload a PDF and STEP file to load the document viewer and CAD model.
          </div>
        ) : activeTab === "pdf" ? (
          <PdfViewer pdfUrl={resolveApiUrl(pdfUrl)} />
        ) : (
          <StepViewer stepUrl={resolveApiUrl(stepUrl)} />
        )}
      </div>
    </main>
  );
}
