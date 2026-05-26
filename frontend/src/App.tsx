import { useState } from "react";
import { createBasicExtraction } from "./lib/api";
import { MetadataPanel } from "./components/MetadataPanel";
import { UploadPanel } from "./components/UploadPanel";
import { ViewerTabs } from "./components/ViewerTabs";
import type { BasicExtraction } from "./types/basicExtraction";

function App() {
  const [pdfFile, setPdfFile] = useState<File | null>(null);
  const [stepFile, setStepFile] = useState<File | null>(null);
  const [activeTab, setActiveTab] = useState<"pdf" | "step">("step");
  const [extraction, setExtraction] = useState<BasicExtraction | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const handleExtract = async () => {
    if (!pdfFile || !stepFile) {
      return;
    }

    setLoading(true);
    setError(null);
    try {
      const nextExtraction = await createBasicExtraction(pdfFile, stepFile, true);
      setExtraction(nextExtraction);
      setActiveTab("step");
    } catch (extractError) {
      setError(extractError instanceof Error ? extractError.message : "Extraction failed.");
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="app-frame">
      <header className="top-bar">
        <div className="brand-lockup">
          <div className="brand-mark">A</div>
          <div>
            <strong>Aether Extract</strong>
            <span>PDF + CAD review workspace</span>
          </div>
        </div>
        <div className="run-state">
          <span className={extraction ? "state-dot complete" : "state-dot"} />
          {extraction ? "Extraction complete" : "Ready for upload"}
        </div>
      </header>

      <div className="app-shell">
        <UploadPanel
          pdfFile={pdfFile}
          stepFile={stepFile}
          loading={loading}
          error={error}
          onPdfChange={setPdfFile}
          onStepChange={setStepFile}
          onSubmit={handleExtract}
        />
        <ViewerTabs
          activeTab={activeTab}
          onTabChange={setActiveTab}
          pdfUrl={extraction?.viewer_files.pdf_url}
          stepUrl={extraction?.viewer_files.step_url}
          partLabel={
            extraction
              ? `${extraction.part.final_part_no ?? extraction.part.part_number ?? "Part"} · ${extraction.part.part_name ?? "Unnamed"}`
              : null
          }
        />
        <MetadataPanel extraction={extraction} />
      </div>
    </div>
  );
}

export default App;
