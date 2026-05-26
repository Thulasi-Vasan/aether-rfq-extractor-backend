export type WarningSeverity = "info" | "warning" | "error";

export interface ExtractionWarning {
  code: string;
  message: string;
  severity: WarningSeverity;
  page_number: number | null;
  details: Record<string, unknown>;
}

export interface BasicSourceNote {
  field: string;
  source_file: string;
  source_type: "pdf" | "step" | "derived" | "internal_mapping";
  note: string;
}

export interface BasicExtraction {
  extraction_id: string;
  part: {
    final_part_no: string | null;
    part_number: string | null;
    revision: string | null;
    part_name: string | null;
    stage: string | null;
    drawing_category: string | null;
    state: string | null;
    project_name: string | null;
    company: string | null;
  };
  material: {
    spec_number: string | null;
    title: string | null;
    density_g_per_cm3: number | null;
    density_source: string | null;
  };
  bom: {
    child_part_count: number;
    children: Array<{
      part_number: string;
      name: string | null;
      quantity: number | string | null;
      unit_of_measure: string | null;
      method_of_use: string | null;
    }>;
  };
  cad: {
    step_product_number: string | null;
    units: string | null;
    bounding_box_mm: {
      x_min: number;
      y_min: number;
      z_min: number;
      x_max: number;
      y_max: number;
      z_max: number;
      length: number;
      width: number;
      height: number;
    } | null;
    sorted_lbh_mm: number[];
    volume_mm3: number | null;
    volume_cm3: number | null;
    surface_area_mm2: number | null;
    solid_count: number | null;
  };
  mass: {
    declared_mass_kg: number | null;
    estimated_mass_kg: number | null;
    implied_density_g_per_cm3: number | null;
    density_g_per_cm3: number | null;
    derivation: string | null;
    notes: string[];
  };
  viewer_files: {
    pdf_url: string;
    step_url: string;
  };
  sources: BasicSourceNote[];
  warnings: ExtractionWarning[];
}
