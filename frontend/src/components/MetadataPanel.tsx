import { AlertTriangle, Box, Factory, FileStack, Info, Ruler, Scale } from "lucide-react";
import type React from "react";
import { formatNumber, formatValue } from "../lib/format";
import type { BasicExtraction, BasicSourceNote } from "../types/basicExtraction";

interface MetadataPanelProps {
  extraction: BasicExtraction | null;
}

export function MetadataPanel({ extraction }: MetadataPanelProps) {
  return (
    <aside className="side-panel metadata-panel">
      <div className="panel-heading">
        <div>
          <p className="eyebrow">Extracted information</p>
          <h2>{extraction?.part.final_part_no ?? "No data loaded"}</h2>
        </div>
        <Info size={18} />
      </div>

      {!extraction ? (
        <div className="empty-details">
          Extracted part, material, BOM, CAD, and mass details will appear here after upload.
        </div>
      ) : (
        <>
          <div className="summary-grid">
            <SummaryMetric label="LBH" value={formatLbh(extraction.cad.sorted_lbh_mm, extraction.cad.units)} />
            <SummaryMetric label="Volume" value={formatVolume(extraction) ?? "Not found"} />
            <SummaryMetric label="Mass Est." value={formatMass(extraction.mass.estimated_mass_kg) ?? "Not found"} />
          </div>

          <DetailSection title="Part" icon={<Factory size={16} />}>
            <Metric label="Final Part No" value={extraction.part.final_part_no} source={sourceFor(extraction, "part")} />
            <Metric label="Revision" value={extraction.part.revision} />
            <Metric label="Part Name" value={extraction.part.part_name} />
            <Metric label="Stage" value={extraction.part.stage} />
            <Metric label="State" value={extraction.part.state} />
          </DetailSection>

          <DetailSection title="Material" icon={<FileStack size={16} />}>
            <Metric label="Spec" value={extraction.material.spec_number} />
            <Metric label="Title" value={extraction.material.title} />
            <Metric
              label="Density"
              value={
                extraction.material.density_g_per_cm3 === null
                  ? null
                  : `${formatNumber(extraction.material.density_g_per_cm3, 4)} g/cm3`
              }
              source={sourceFor(extraction, "material.density_g_per_cm3")}
            />
            <Metric label="Density Source" value={extraction.material.density_source} />
          </DetailSection>

          <DetailSection title="BOM" icon={<Box size={16} />}>
            <Metric label="Child Part Count" value={extraction.bom.child_part_count} source={sourceFor(extraction, "bom")} />
            {extraction.bom.children.length ? (
              <div className="bom-list">
                {extraction.bom.children.map((child) => (
                  <div className="bom-row" key={child.part_number}>
                    <strong>{child.part_number}</strong>
                    <span>{formatValue(child.name)}</span>
                    <small>
                      Qty {formatValue(child.quantity)} · {formatValue(child.method_of_use)}
                    </small>
                  </div>
                ))}
              </div>
            ) : (
              <p className="muted-line">No BOM children found.</p>
            )}
          </DetailSection>

          <DetailSection title="CAD Geometry" icon={<Ruler size={16} />}>
            <Metric label="STEP Product" value={extraction.cad.step_product_number} source={sourceFor(extraction, "cad")} />
            <Metric label="Units" value={extraction.cad.units} />
            <Metric label="LBH" value={formatLbh(extraction.cad.sorted_lbh_mm, extraction.cad.units)} />
            <Metric label="Volume" value={formatVolume(extraction)} />
            <Metric
              label="Surface Area"
              value={
                extraction.cad.surface_area_mm2 === null
                  ? null
                  : `${formatNumber(extraction.cad.surface_area_mm2, 2)} mm2`
              }
            />
            <Metric label="Solid Count" value={extraction.cad.solid_count} />
          </DetailSection>

          <DetailSection title="Mass" icon={<Scale size={16} />}>
            <Metric label="Declared" value={formatMass(extraction.mass.declared_mass_kg)} />
            <Metric label="Estimated" value={formatMass(extraction.mass.estimated_mass_kg)} source={sourceFor(extraction, "mass.estimated_mass_kg")} />
            <Metric label="Derivation" value={extraction.mass.derivation} />
            {extraction.mass.notes.map((note) => (
              <p className="note-line" key={note}>{note}</p>
            ))}
          </DetailSection>

          {extraction.warnings.length ? (
            <DetailSection title="Warnings" icon={<AlertTriangle size={16} />}>
              {extraction.warnings.map((warning) => (
                <div className="warning-row" key={`${warning.code}-${warning.message}`}>
                  <strong>{warning.code}</strong>
                  <span>{warning.message}</span>
                </div>
              ))}
            </DetailSection>
          ) : null}
        </>
      )}
    </aside>
  );
}

interface DetailSectionProps {
  title: string;
  icon: React.ReactNode;
  children: React.ReactNode;
}

function DetailSection({ title, icon, children }: DetailSectionProps) {
  return (
    <section className="detail-section">
      <h3>
        {icon}
        {title}
      </h3>
      {children}
    </section>
  );
}

interface MetricProps {
  label: string;
  value: string | number | null | undefined;
  source?: BasicSourceNote;
}

function Metric({ label, value, source }: MetricProps) {
  return (
    <div className="metric-row">
      <span>{label}</span>
      <strong>
        {formatValue(value)}
        {source ? <SourceBadge source={source} /> : null}
      </strong>
    </div>
  );
}

function SourceBadge({ source }: { source: BasicSourceNote }) {
  return (
    <span className={`source-badge source-${source.source_type}`} tabIndex={0}>
      ?
      <span className="source-tooltip" role="tooltip">
        <span>
          <b>Source</b>
          {sourceLabel(source.source_type)}
        </span>
        <span>
          <b>File</b>
          {source.source_file}
        </span>
        <span>
          <b>Note</b>
          {source.note}
        </span>
      </span>
    </span>
  );
}

function sourceLabel(sourceType: BasicSourceNote["source_type"]): string {
  switch (sourceType) {
    case "pdf":
      return "PDF";
    case "step":
      return "STEP";
    case "derived":
      return "Derived";
    case "internal_mapping":
      return "Mapping";
    default:
      return sourceType;
  }
}

function SummaryMetric({ label, value }: { label: string; value: string }) {
  return (
    <div className="summary-metric">
      <span>{label}</span>
      <strong>{value}</strong>
    </div>
  );
}

function sourceFor(extraction: BasicExtraction, field: string): BasicSourceNote | undefined {
  return extraction.sources.find((source) => source.field === field);
}

function formatLbh(values: number[], units: string | null): string {
  if (!values.length) {
    return "Not found";
  }
  return `${values.map((value) => formatNumber(value, 3)).join(" x ")} ${units ?? "mm"}`;
}

function formatVolume(extraction: BasicExtraction): string | null {
  if (extraction.cad.volume_cm3 !== null) {
    return `${formatNumber(extraction.cad.volume_cm3, 3)} cm3`;
  }
  if (extraction.cad.volume_mm3 !== null) {
    return `${formatNumber(extraction.cad.volume_mm3, 2)} mm3`;
  }
  return null;
}

function formatMass(value: number | null): string | null {
  return value === null ? null : `${formatNumber(value, 4)} kg`;
}
