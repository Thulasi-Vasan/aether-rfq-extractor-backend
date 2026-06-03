import React, { useState, useRef } from 'react';
import * as ExcelJS from 'exceljs';
import './index.css';

// SVG Icons
const CloudUploadIcon = () => (
  <svg width="48" height="48" viewBox="0 0 24 24" fill="none" xmlns="http://www.w3.org/2000/svg">
    <path d="M17.5 19H6.5C3.46243 19 1 16.5376 1 13.5C1 10.4624 3.46243 8 6.5 8C6.91428 8 7.318 8.04576 7.7061 8.1328C8.5986 5.22816 11.0255 3 14 3C17.866 3 21 6.13401 21 10C21 10.1557 20.9949 10.3101 20.985 10.4632C22.1834 11.2335 23 12.5694 23 14.1C23 16.8062 20.8062 19 18.1 19H17.5" stroke="#12356D" strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round"/>
    <path d="M12 15V10M12 10L9.5 12.5M12 10L14.5 12.5" stroke="#12356D" strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round"/>
  </svg>
);

const SpinnerIcon = () => (
  <svg className="spinner" width="48" height="48" viewBox="0 0 24 24" fill="none" xmlns="http://www.w3.org/2000/svg">
    <circle cx="12" cy="12" r="10" stroke="#ccc" strokeWidth="3" />
    <path d="M12 2C6.47715 2 2 6.47715 2 12" stroke="#12356D" strokeWidth="3" strokeLinecap="round" strokeLinejoin="round" />
  </svg>
);

function getColName(i: number) {
  let name = '';
  let index = i;
  while (index >= 0) {
    name = String.fromCharCode((index % 26) + 65) + name;
    index = Math.floor(index / 26) - 1;
  }
  return name;
}

function parseArgb(argb: string | undefined): string {
  if (!argb) return 'transparent';
  if (argb.length === 8) {
    const a = parseInt(argb.slice(0, 2), 16) / 255;
    const r = parseInt(argb.slice(2, 4), 16);
    const g = parseInt(argb.slice(4, 6), 16);
    const b = parseInt(argb.slice(6, 8), 16);
    return `rgba(${r},${g},${b},${a})`;
  }
  return `#${argb}`;
}

const App = () => {
  const [file, setFile] = useState<File | null>(null);
  const [fileName, setFileName] = useState<string>('');
  const [isUploading, setIsUploading] = useState(false);
  const [isReady, setIsReady] = useState(false);
  const [isProcessing, setIsProcessing] = useState(false);

  const [error, setError] = useState('');
  const [blobUrl, setBlobUrl] = useState<string | null>(null);

  // Excel Viewer State
  const [showViewer, setShowViewer] = useState(false);
  const [workbookData, setWorkbookData] = useState<any>(null);

  const fileInputRef = useRef<HTMLInputElement>(null);

  const handleFileDrop = (e: React.DragEvent<HTMLDivElement>) => {
    e.preventDefault();
    if (e.dataTransfer.files && e.dataTransfer.files.length > 0) {
      handleSelectedFile(e.dataTransfer.files[0]);
    }
  };

  const handleFileChange = (e: React.ChangeEvent<HTMLInputElement>) => {
    if (e.target.files && e.target.files.length > 0) {
      handleSelectedFile(e.target.files[0]);
    }
  };

  const handleSelectedFile = (f: File) => {
    if (!f.name.toLowerCase().endsWith('.pdf')) {
      setError('Please upload a valid .PDF file.');
      return;
    }
    setError('');
    setFile(f);
    setFileName(f.name);
    setIsUploading(true);
    setIsReady(false);

    // Simulate 2 sec upload
    setTimeout(() => {
      setIsUploading(false);
      setIsReady(true);
    }, 2000);
  };

  const processDocument = async () => {
    if (!file) return;
    setIsProcessing(true);
    setError('');
    setBlobUrl(null);

    try {
      const formData = new FormData();
      formData.append('file', file);
      formData.append('force_reextract', 'true');

      const uploadRes = await fetch('http://localhost:8000/v1/documents', {
        method: 'POST',
        body: formData,
      });

      if (!uploadRes.ok) {
        throw new Error(`Upload failed: ${uploadRes.statusText}`);
      }

      const uploadData = await uploadRes.json();
      const documentId = uploadData.document_id;

      const excelRes = await fetch(`http://localhost:8000/v1/documents/${documentId}/export-excel`);

      if (!excelRes.ok) {
        throw new Error(`Excel generation failed: ${excelRes.statusText}`);
      }

      const blob = await excelRes.blob();
      const url = URL.createObjectURL(blob);
      setBlobUrl(url);

      const arrayBuffer = await blob.arrayBuffer();

      const wb = new ExcelJS.Workbook();
      await wb.xlsx.load(arrayBuffer);

      let ws = wb.getWorksheet('Input Sheet');
      if (!ws) {
          const wsId = wb.worksheets.length > 0 ? wb.worksheets[0].id : null;
          ws = wsId !== null ? wb.getWorksheet(wsId) : undefined;
      }

      if (!ws) throw new Error("No worksheets found in the Excel document.");

      // Parse Excel into structured grid
      const grid: any[] = [];
      const merges: any = {}; // map top-left cell coord -> { colspan, rowspan }
      const skipCells = new Set<string>();

      const wsModel = ws as any;
      const mergeList = wsModel.model?.merges || [];

      mergeList.forEach((rangeStr: string) => {
         const [start, end] = rangeStr.split(':');
         const startCell = ws!.getCell(start);
         const endCell = ws!.getCell(end);
         const sRow = Number(startCell.row);
         const sCol = Number(startCell.col);
         const eRow = Number(endCell.row);
         const eCol = Number(endCell.col);

         const rspan = eRow - sRow + 1;
         const cspan = eCol - sCol + 1;
         merges[`${sRow}-${sCol}`] = { rspan, cspan };

         for (let r = sRow; r <= eRow; r++) {
             for (let c = sCol; c <= eCol; c++) {
                 if (r === sRow && c === sCol) continue;
                 skipCells.add(`${r}-${c}`);
             }
         }
      });

      const maxRow = ws.rowCount || 1;
      const maxCol = ws.columnCount || 1;
      const colsWidth = [];

      for (let c = 1; c <= maxCol; c++) {
          const w = ws.getColumn(c).width || 12;
          colsWidth.push(w * 8); // approximate width
      }

      for (let r = 1; r <= maxRow; r++) {
        const row = ws.getRow(r);
        const rowData = [];
        for (let c = 1; c <= maxCol; c++) {
          const cellId = `${r}-${c}`;
          if (skipCells.has(cellId)) continue;

          const cell = row.getCell(c);
          let value = cell.value;
          if (value !== null && typeof value === 'object') {
              if ('result' in value) {
                  value = value.result;
                  if (value !== null && typeof value === 'object' && 'error' in value) {
                      value = value.error;
                  }
              } else if ('richText' in value) {
                  value = value.richText.map((rt: any) => rt.text).join('');
              } else if ('hyperlink' in value) {
                  value = value.text || value.hyperlink;
              } else if ('error' in value) {
                  value = value.error;
              } else if (value instanceof Date) {
                  value = value.toLocaleDateString();
              } else {
                  value = cell.text || '';
              }
          }

          if (value instanceof Date) {
              value = value.toLocaleDateString();
          }

          // Use formatted text if available (exceljs cell.text)
          if (cell.text && typeof value === 'number') {
             value = cell.text;
          }

          let bgColor = 'transparent';
          if (cell.fill && cell.fill.type === 'pattern') {
             if (cell.fill.fgColor && cell.fill.fgColor.argb) {
                 bgColor = parseArgb(cell.fill.fgColor.argb);
             }
             // Sometimes patterned fills are black by default or FFFFFFFF is transparent in a weird way
             if (bgColor === 'rgba(255,255,255,0)') bgColor = 'transparent';
          }

          let color = '#000';
          let bold = false;
          let fontSize = '13px';
          let alignH = 'left';
          let alignV = 'bottom';
          let borderStr = '1px solid #e0e0e0';

          if (cell.font) {
              if (cell.font.color?.argb) color = parseArgb(cell.font.color.argb);
              bold = !!cell.font.bold;
              if (cell.font.size) fontSize = `${cell.font.size * 1.33}px`; // points to px approx
          }
          if (cell.alignment) {
              if (cell.alignment.horizontal) alignH = cell.alignment.horizontal;
              if (cell.alignment.vertical) alignV = cell.alignment.vertical;
          }

          // Borders
          let borderBottom = borderStr, borderTop = borderStr, borderLeft = borderStr, borderRight = borderStr;
          if (cell.border) {
              if (cell.border.bottom?.style) borderBottom = '1px solid #666';
              if (cell.border.top?.style) borderTop = '1px solid #666';
              if (cell.border.left?.style) borderLeft = '1px solid #666';
              if (cell.border.right?.style) borderRight = '1px solid #666';
          }

          const mergeData = merges[cellId];

          rowData.push({
             value,
             colSpan: mergeData ? mergeData.cspan : 1,
             rowSpan: mergeData ? mergeData.rspan : 1,
             style: {
                 backgroundColor: bgColor,
                 color,
                 fontWeight: bold ? 'bold' : 'normal',
                 fontSize,
                 textAlign: alignH as any,
                 verticalAlign: alignV as any,
                 borderBottom,
                 borderTop,
                 borderLeft,
                 borderRight,
                 padding: '4px 8px',
                 overflow: 'hidden',
                 textOverflow: 'ellipsis',
                 whiteSpace: cell.alignment?.wrapText ? 'normal' : 'nowrap'
             }
          });        }
        grid.push({ height: (row.height || 15) * 1.5, cells: rowData });
      }

      setWorkbookData({ grid, colsWidth });
      setShowViewer(true);
    } catch (err: any) {
      setError(err.message || 'An error occurred during processing.');
    } finally {
      setIsProcessing(false);
    }
  };

  if (showViewer && workbookData) {
      return (
          <div className="viewer-layout">
              <div className="viewer-header">
                  <h2>{fileName.replace('.pdf', '')}_exported.xlsx</h2>
                  {blobUrl && (
                      <a href={blobUrl} download={`${fileName.replace('.pdf', '')}_exported.xlsx`} style={{ textDecoration: 'none' }}>
                          <button className="btn-primary" style={{ padding: '8px 16px' }}>Download</button>
                      </a>
                  )}
              </div>
              <div className="viewer-content">
                 <table className="excel-table">
                     <thead>
                         <tr>
                             <th className="excel-corner"></th>
                             {workbookData.colsWidth.map((w: number, i: number) => (
                                 <th key={i} style={{ width: w, minWidth: w, maxWidth: w }}>
                                     {getColName(i)}
                                 </th>
                             ))}
                         </tr>
                     </thead>
                     <tbody>
                         {workbookData.grid.map((r: any, rIdx: number) => (
                             <tr key={rIdx} style={{ height: r.height }}>
                                 <td className="excel-row-header">{rIdx + 1}</td>
                                 {r.cells.map((c: any, cIdx: number) => (
                                     <td key={cIdx} colSpan={c.colSpan} rowSpan={c.rowSpan} style={c.style}>
                                         {c.value !== null && c.value !== undefined ? String(c.value) : ''}
                                     </td>
                                 ))}
                             </tr>
                         ))}
                     </tbody>
                 </table>
              </div>
          </div>
      );
  }

  return (
    <div className="container">
      <div className="card-layout">
         <div className="card-body">
            {error && <div className="error-message">{error}</div>}

            <div
              className={`dropzone ${isUploading ? 'uploading' : ''}`}
              onDragOver={(e) => e.preventDefault()}
              onDrop={handleFileDrop}
              onClick={() => !isUploading && fileInputRef.current?.click()}
            >
                <input
                  type="file"
                  accept=".pdf"
                  onChange={handleFileChange}
                  ref={fileInputRef}
                  style={{ display: 'none' }}
                />

                {isUploading ? (
                    <div className="upload-state">
                        <SpinnerIcon />
                        <p>Uploading pdf...</p>
                    </div>
                ) : (
                    <div className="upload-state">
                        <CloudUploadIcon />
                        <h3>Click or drag to upload engineering inputs.</h3>
                        <p>Must be a .PDF file</p>
                    </div>
                )}
            </div>

            {fileName && !isUploading && (
                <div style={{ marginTop: '16px', color: '#12356D', fontWeight: '500' }}>
                    Selected: {fileName}
                </div>
            )}

            <button
              className="btn-primary start-btn"
              onClick={processDocument}
              disabled={!isReady || isProcessing}
              style={{ marginTop: '24px' }}
            >
              {isProcessing ? 'Processing...' : 'Start processing'}
            </button>
         </div>
      </div>
    </div>
  );
}

export default App;
