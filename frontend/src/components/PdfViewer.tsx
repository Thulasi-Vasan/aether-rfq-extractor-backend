import { ExternalLink, FileText, Loader2 } from "lucide-react";
import { useEffect, useState } from "react";

interface PdfViewerProps {
  pdfUrl: string;
}

export function PdfViewer({ pdfUrl }: PdfViewerProps) {
  const [objectUrl, setObjectUrl] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    let disposed = false;
    let nextObjectUrl: string | null = null;

    async function loadPdf() {
      setObjectUrl(null);
      setError(null);
      try {
        const response = await fetch(pdfUrl);
        if (!response.ok) {
          throw new Error(`Could not load PDF: HTTP ${response.status}`);
        }
        const blob = await response.blob();
        nextObjectUrl = URL.createObjectURL(new Blob([blob], { type: "application/pdf" }));
        if (!disposed) {
          setObjectUrl(nextObjectUrl);
        }
      } catch (loadError) {
        if (!disposed) {
          setError(loadError instanceof Error ? loadError.message : "Could not load PDF.");
        }
      }
    }

    loadPdf();

    return () => {
      disposed = true;
      if (nextObjectUrl) {
        URL.revokeObjectURL(nextObjectUrl);
      }
    };
  }, [pdfUrl]);

  if (error) {
    return (
      <div className="empty-viewer">
        <FileText size={24} />
        <span>{error}</span>
        <a href={pdfUrl} target="_blank" rel="noreferrer">
          Open PDF in a new tab
          <ExternalLink size={14} />
        </a>
      </div>
    );
  }

  if (!objectUrl) {
    return (
      <div className="empty-viewer">
        <Loader2 className="spin" size={22} />
        Loading PDF...
      </div>
    );
  }

  return <iframe className="pdf-frame" src={objectUrl} title="Uploaded PDF drawing" />;
}
