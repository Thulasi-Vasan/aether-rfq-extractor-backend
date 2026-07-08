# Next-Generation Classification Prompt Tuning Plan

Based on the recent analysis and the expert breakdown of how a human manufacturing engineer segregates turbocharger compressor housings, we need to move beyond isolated, zero-shot visual classification.

## 1. Issue: Misclassification of Casting STEP Files
**Problem**: The current `CAD_CLASSIFICATION_PROMPT_TMPL` relies heavily on visual descriptors ("organic B-spline surfaces", "fillets everywhere"). VLMs struggle to reliably distinguish a near-net-shape casting CAD model from a finished machined CAD model based purely on a 2D isometric render, as both might contain curves or sharp edges depending on the render angle.

**Proposed Solution**:
1. **Inherit Classification via Filename Matching (Primary)**: Do not classify STEP files in isolation. A STEP file (e.g., `6503850_Rev_2.stp`) should automatically inherit the classification of its corresponding PDF drawing (`6503850_Rev_2.pdf`). If the PDF is determined to be the raw casting, the STEP file is the raw casting model.
2. **Refine VLM Visual Fallback (Secondary)**: If an orphaned STEP file exists without a matching PDF, the prompt must explicitly define the difference functionally, not just aesthetically:
   - *Casting*: Lacks mounting holes, lacks threaded features, and lacks flat, precision-mating surfaces. It represents the unmachined slug.
   - *Machining*: Features precision drilled/tapped holes, flat mounting flanges, and geometric cutouts added after the casting process.

## 2. Issue: Single-File vs. Batch-Level Graph Reasoning
**Problem**: Classifying documents in isolation is fundamentally flawed for this domain. For example, part `6503850` and `6511292` might both be titled "HOUSING, COMPRESSOR" with similar geometries. Looking at them individually leads to hallucination. A human engineer looks at the **BOM (Bill of Materials)**: if `6511292` lists `6503850` as its raw input material, then `6503850` is the Die Casting and `6511292` is the Finish Machining. 

**Proposed Solution: Graph-Based Classification Pipeline**
Instead of feeding one file at a time to the VLM, we must redesign the classification pipeline to execute in three phases:

### Phase 1: Information Extraction (All PDFs)
Run a focused prompt on all PDFs in the batch to extract structured metadata:
- **Part Number**
- **Part Name**
- **Explicit Category** (if stated, e.g., "CASTING", "TABULATION")
- **BOM Table Inputs** (What raw material part numbers does this drawing consume?)

### Phase 2: BOM Graph Resolution & Classification
Construct a relationship graph across the batch using the extracted data:
- **Die Casting**: Identify the "leaf nodes" (parts that are consumed as raw materials by other drawings in the batch) or drawings that explicitly call out casting alloys/specs.
- **Machining**: Identify the "parent nodes" (drawings whose BOM consumes the castings). Confirm with GD&T and setup notes.
- **Assembly**: Look for top-level drawings that consume multiple machined components or contain exploded views. (Note: Acknowledge the edge case where no true assembly drawing exists; do not force a machining drawing into the assembly bucket unless it fits).
- **Edge Cases**: Flag duplicates (e.g., `_copy.pdf`), superseded revisions in the same folder, and missing dependencies.

### Phase 3: Final File Tagging
- Assign the computed categories to each PDF.
- Map all 3D CAD files (`.step`, `.stp`) to their parent PDFs using Part Number filename matching.
- Any orphaned files undergo the refined VLM visual fallback classification.

## Execution Requirements
To implement this, we will need to:
1. Create a new `BatchClassificationAgent` or modify `VLMClassificationService` to accept a list of files rather than a single file.
2. Add a new prompt `PDF_METADATA_EXTRACTION_PROMPT` to pull the BOM/Title block data.
3. Add a dependency-graph resolution algorithm in Python before returning the final `ZipClassificationResponse`.
