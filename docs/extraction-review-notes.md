# PDF Extraction Review Notes

This document tracks extraction issues found by manual review of the reference PDF and the current backend JSON output. Use it as the working reference for improving table reconstruction and frontend-ready responses.

## Sources

- Reference PDF: `samples/meridian-housing-gdc-reference.pdf`
- Current JSON response: `samples/response.json`
- Current page 1 table in JSON: `table_id = p1_t1`

## Page 1 Issues

### 1. Vertical Text Extracted In Reverse Order

**PDF location**

- Page 1
- `Capital Investments (Rs. Lac)` table
- Left-side vertical group label: `Sand core`

**Expected behavior**

- The vertically positioned label should be represented as readable text:
  - `Sand core`
- It should be associated with the rows it visually spans.

**Current JSON behavior**

- In `samples/response.json`, the label appears as:

```json
"text": "eroc\ndnaS"
```

**Problem**

- Vertical text is extracted in reverse reading order.
- This issue is expected to repeat anywhere the PDF has vertically rotated labels.

**Likely cause**

- The extractor currently trusts pdfplumber's extracted cell text order.
- Rotated text needs special handling because the character/word order can be emitted bottom-to-top or reversed.

**Fix direction**

- Detect rotated or vertical text using character/word geometry.
- Normalize vertical text by sorting glyphs/words in visual reading order.
- Apply this before final cell text assignment.

---

### 2. Common/Merged Cell Values Are Not Propagated Across Covered Rows

**PDF location**

- Page 1
- `Capital Investments (Rs. Lac)` table
- Rows:
  - `Core shooting M/c -1`
  - `Core shooting M/c -2`
- Shared value:
  - `1` under `No of M/cs / No of Units`

**Expected behavior**

- The value `1` should be represented as a shared/merged cell that covers both related rows.
- The frontend should either receive:
  - one cell with `rowspan > 1`, or
  - propagated values with metadata showing the value came from a merged source cell.

**Current JSON behavior**

- The value is assigned only to the first row.
- The following visually covered row is empty.
- Similar missing shared values are expected in other parts of the document.

**Problem**

- Merged/common values are visually present in the PDF but not preserved in the normalized table grid.
- This can make the rendered frontend table look like values are missing.

**Likely cause**

- Current span handling is best-effort and defaults to `rowspan = 1`, `colspan = 1`.
- pdfplumber may emit the merged area as one cell or assign text to only one grid row.
- The normalizer does not yet infer or propagate visual row spans.

**Fix direction**

- Use cell bounding boxes to detect cells that vertically cover multiple row bands.
- Set `rowspan` when a detected cell spans multiple row boundaries.
- Optionally add a frontend-friendly `source_cell_id` or `is_span_continuation` marker if values are propagated.

---

### 3. Testing Cost Details Region Is Extracted As One Large Cell And Also As Individual Rows

**PDF location**

- Page 1
- `Testing Cost Details: (Rs.)` section

**Expected behavior**

- This section should be reconstructed as a clean two-column table:
  - testing cost label
  - value
- Example rows:
  - `Chemical Testing cost/ part` -> `4.0`
  - `Tensile Testing cost / part` -> `5.8`
  - `Microstructure Testing cost / part` -> `6.5`
  - `Total Testing Cost/ Part` -> `17.2`

**Current JSON behavior**

- A large merged text block appears in row 56:

```json
"text": "Testing Cost Details: (Rs.)\nChemical Testing cost/ part 4.0\nX Ray Testing cost / part\nTensile Testing cost / part 5.8\nMicrostructure Testing cost / part 6.5\nHardness Testing cost / part 0.1\n3D Inspection cost / part 0.8\nPorosity Testing cost / part\nOthers (if any)\nTotal Testing Cost/ Part 17.2"
```

- The same section is also partially extracted into individual row/column cells later:
  - `Chemical Testing cost/ part` with `4.0`
  - `Hardness Testing cost / part` with `0.1`
  - `Total Testing Cost/ Part` with `17.2`

**Problem**

- The frontend may show duplicate data:
  - one large combined cell
  - separate row-wise cells
- The combined cell is not useful for table rendering.

**Likely cause**

- The detected table region on page 1 is too large and includes multiple sub-tables/sections.
- Some drawn borders or merged header areas cause pdfplumber to treat the full section as a single large cell.
- The current normalizer does not split nested/sub-table regions.

**Fix direction**

- Segment large detected tables into smaller logical regions before normalization.
- Detect section headers like `Testing Cost Details: (Rs.)`.
- Prefer row-wise cells when both a large aggregate cell and detailed rows exist.
- Add a duplicate/overlap suppression pass for cells whose text fully contains later row-level cells.

---

### 4. Footer Text Is Overlapped And Collapsed Into Garbled Text

**PDF location**

- Page 1 footer area
- Around:
  - `Classification: Confidential`
  - `This estimation is valid for 90 days only`
  - `F/PED-EST/03 Rev. No. 01 Rev. Dt. 08.10.2014`

**Expected behavior**

- Footer text should be extracted as separate text elements or page footer metadata.
- It should not be merged into table cells.
- It should not be interleaved with overlapping text from another line.

**Current JSON behavior**

- In `samples/response.json`, row 68 contains:

```json
"text": "cTahtiiso ne:s Ctimonaftiidoenn itsia vlalid for 90 days only F/PED-EST/03 Rev. No. 01 Rev. Dt. 08.10.2014"
```

**Problem**

- Multiple footer lines overlap into a single garbled sentence.
- This makes the extracted text unreadable and pollutes the table output.

**Likely cause**

- Footer content is included inside the detected page-level table region.
- Text with overlapping y-coordinates is being merged without separating footer bands.
- Repeated headers/footers are not yet excluded or flagged before table normalization.

**Fix direction**

- Add repeated header/footer detection before table extraction output is finalized.
- Exclude footer bands from table regions unless the table genuinely extends to the footer.
- Preserve footer text separately under page metadata or `document.footers`.
- Add overlap-aware line grouping so text from different baselines is not interleaved.

## Page 2 Issues

> Review note: the screenshots for this review page match the machining estimation page. In the current JSON response, this content is under `page_number = 3`, with tables `p3_t1` through `p3_t5`. The actual PDF page 2 is image-only in the current extraction.

### 1. Summary Row Is Extracted Twice

**PDF location**

- Machining estimation page
- Bottom of the main machining table
- Green summary row containing:
  - `Cell Cycle Time:`
  - `7.00`
  - `Total Capital Expenditure`
  - `2,97,00,000`

**Expected behavior**

- The summary row should be represented once as structured table cells:
  - `Cell Cycle Time:` -> `7.00`
  - `Total Capital Expenditure` -> `2,97,00,000`
- It should not also appear as one combined aggregate sentence.

**Current JSON behavior**

- In `samples/response.json`, `p3_t1` row 21 contains the full row as one large cell:

```json
"text": "Cell Cycle Time: 7.00 Total Capital Expenditure 2,97,00,000"
```

- The next row also extracts the same content as separate cells:

```json
["", "", "Cell Cycle Time:", "7.00", "Total Capital Expenditure", "", "", "2,97,00,000"]
```

**Problem**

- The same row is duplicated in two forms:
  - aggregate sentence
  - structured cells
- This can cause the frontend to show duplicate data.

**Likely cause**

- The detected table includes a merged/filled summary band.
- pdfplumber returns both the large merged-region text and the lower-level cell text.
- The normalizer does not yet suppress aggregate cells when equivalent detailed cells are available.

**Fix direction**

- Add duplicate aggregate-cell suppression.
- If a large cell's text is mostly composed of text found in sibling cells or the next row, prefer the structured cells.
- Add warning code `duplicate_aggregate_cell_suppressed` when this cleanup happens.

---

### 2. Operating Cost Section Is Both Aggregated And Separately Extracted

**PDF location**

- Machining estimation page
- `Operating cost for the given Volume: (Cost in Rs.)`
- Visually this area contains multiple table blocks:
  - left-side operating cost table
  - right-side cell/capacity/utilisation table
  - right-side power/manpower/floor/IMP/setup/variant table

**Expected behavior**

- The area should be split into separate frontend-renderable tables or at least separate logical table groups.
- Example left table rows:
  - `Cost of Cutting tools` -> `3,63,000`
  - `Cost of Tool Holders` -> `22,00,000`
  - `Cost of Fixtures` -> `23,00,000`
  - `Total Operating Cost` -> `59,06,162`
- Example right table rows:
  - `Cell Cycle Time (Min.)` -> `7.00`
  - `Cell Capacity (Nos.)` -> `43,682`
  - `Cell Utilisation` -> `83%`
  - `No. of Cells` -> `1`

**Current JSON behavior**

- In `samples/response.json`, `p3_t1` row 24 stores the full area as one combined cell:

```json
"text": "Operating cost for the given Volume: (Cost in Rs.)\nCost of Cutting tools 3,63,000 Cell Cycle Time (Min.) 7.00\nCost of Tool Holders 22,00,000 Cell Capacity (Nos.) 43,682\nCost of Probing Unit (if any) Cell Utilisation 83%\nCost of Fixtures 23,00,000 No. of Cells 1\nCost of Gauges 6,80,000\nCost of Material Handling 3,00,000 Power rating for cell (kw/hr) 115.0\nMan Power / Shift / Cell 2\nCoolant oil cost 41,382 Floor area required / cell(Sq.M) 226.0\nDM water cost for coolant, washing & Leak 21,780 IMP Salvaging % 0%\nBarcode label recurring cost Setup changeover considered (Y/ N) N\nImpregnation Basket cost 0 No of variants planned / cell 1\nTotal Oerating Cost 59,06,162"
```

- The extractor also creates smaller tables for parts of the same area:
  - `p3_t2`: left operating-cost rows such as `Cost of Cutting tools`
  - `p3_t3`: right cell-cycle/capacity table
  - `p3_t4`: right power/manpower/floor table
  - `p3_t5`: lower left rows including `Total Oerating Cost`

**Problem**

- This is not a complete miss of the individual tables.
- The individual values are partially/mostly extracted into separate two-column tables.
- The issue is duplication and hierarchy:
  - `p3_t1` keeps the same operating-cost area as one large aggregate sentence.
  - `p3_t2` through `p3_t5` also expose the same content as individual tables.
- The frontend may render both the combined paragraph and the separate child tables unless the aggregate parent cell is suppressed.

**Likely cause**

- The page contains multiple adjacent table blocks inside a larger bordered region.
- Current extraction accepts both parent-level and child-level detections.
- There is no hierarchy/overlap resolution between parent table regions and nested logical tables.

**Fix direction**

- Add table-region hierarchy detection.
- If smaller child tables cover the content of a large parent aggregate cell, suppress the aggregate cell or split the parent.
- Segment this area using vertical whitespace and independent border boxes.
- Prefer separate logical tables for side-by-side sections instead of one wide combined text block.
- Add warning code `nested_table_region_detected` when parent/child table overlap is found.

---

### 3. Stacked Operating Cost Blocks Should Be One Logical Table

**PDF location**

- Machining estimation page
- `Operating cost for the given Volume: (Cost in Rs.)`
- Left-side operating-cost section
- Visually split into an upper block and a lower block with whitespace between them.

**Expected behavior**

- The upper and lower blocks should be treated as one logical operating-cost table.
- The `Total Oerating Cost` / `Total Operating Cost` row belongs to the full operating-cost section, not only to the lower block.
- Expected logical row sequence:
  - `Cost of Cutting tools` -> `3,63,000`
  - `Cost of Tool Holders` -> `22,00,000`
  - `Cost of Probing Unit (if any)` -> empty
  - `Cost of Fixtures` -> `23,00,000`
  - `Cost of Gauges` -> `6,80,000`
  - `Cost of Material Handling` -> `3,00,000`
  - `Coolant oil cost` -> `41,382`
  - `DM water cost for coolant, washing & Leak` -> `21,780`
  - `Barcode label recurring cost` -> empty
  - `Impregnation Basket cost` -> `0`
  - `Total Oerating Cost` -> `59,06,162`

**Current JSON behavior**

- The upper operating-cost block is extracted as `p3_t2`.
- The lower operating-cost block is extracted as `p3_t5`.
- `Total Oerating Cost` is currently attached only to `p3_t5`.

**Problem**

- The frontend may render the operating-cost section as two separate tables even though it is one logical table.
- The total row visually/logically summarizes both blocks, but its current table grouping makes it look tied only to the lower block.

**Likely cause**

- `pdfplumber` detects the upper and lower blocks as separate tables because of the vertical whitespace/gap between them.
- The current normalizer does not merge vertically stacked table fragments.

**Fix direction**

- Add a logical table-continuation merge pass after duplicate aggregate suppression.
- Merge vertically stacked tables when:
  - they are on the same page
  - their x positions and widths are closely aligned
  - their column counts and column boundaries are compatible
  - the vertical gap is within a configured threshold
  - the lower table has continuation/total rows for the same section
- For this page, `p3_t2` and `p3_t5` should likely become one logical operating-cost table.
- Add warning/metadata code `stacked_table_merged` when this merge occurs.

## Page 4 Issues

> Preliminary note: page 4 is the process planning page. The current JSON response exposes only one detected table, `p4_t1`, which is the RFQ/header metadata table. The page itself contains images/process visuals plus nearby text.

### 1. Image/Process Area Is Not Extracted Into Useful Structured Output

**PDF location**

- Page 4
- Process planning/image area below the RFQ header
- Visual content includes process images/markings and related text labels.

**Expected behavior**

- For frontend review, the backend should eventually expose useful content from this area:
  - image metadata
  - OCR/vision-derived text from image regions
  - nearby vector text labels, if they exist outside the image
  - source bboxes for each extracted visual/text element

**Current JSON behavior**

- `samples/response.json` only contains one table for this page:
  - `p4_t1`
  - title: `SCL-PED RFQ Process Planning Sheet`
  - rows: RFQ metadata/header fields only
- The process/image area is not represented as a structured table or page element in the current frontend table response.

**Problem**

- Important process-planning visual content is not available to the frontend.
- Any text embedded inside image pixels cannot be extracted by the current vector/table-only pipeline.
- Some surrounding vector text may exist, but the current response schema is table-focused and does not expose non-table text elements.

**Likely cause**

- OCR is intentionally out of scope for v1.
- Vision extraction is not implemented.
- The API currently returns extracted tables, not a full page element model.

**Fix direction**

- Keep this out of the table-only v1 fix scope unless required immediately.
- Add a future OCR/vision phase for image-heavy pages.
- Add page-level non-table text output if frontend needs text near images before OCR is available.
- Add warning code `image_region_not_ocr_processed` for pages with images and low table coverage.

---

## Page 5 Issues

> Preliminary note: page 5 currently appears as one large assembly table, `p5_t1`. Some repeated values may be real because the PDF has separate `Assembly` and `After Assembly Machining` columns/sections, but the current extraction still needs review for duplication and footer overlap.

### 1. Values May Be Repeated Within The Large Assembly Table

**PDF location**

- Page 5
- `RFQ ESTIMATION FOR ASSEMBLY`
- Large assembly/after-assembly machining table

**Expected behavior**

- Values should appear only where they visually belong.
- If the same value appears in multiple process sections, the JSON should make that section/column context clear.
- The frontend should not show accidental duplicates caused by aggregate cells or repeated footer/header content.

**Current JSON behavior**

- `samples/response.json` has one page 5 table:
  - `p5_t1`
  - rows: `57`
  - columns: `5`
- Several values appear repeatedly in different rows/sections, for example:
  - `0.0`
  - `0.00`
  - `0`
  - `1.0`
- Some of these are likely legitimate because the PDF compares `Assembly` and `After Assembly Machining`, but the current extraction does not clearly distinguish whether every repeated value is intentional.

**Problem**

- Manual review suggests page 5 values may be duplicated.
- Because `p5_t1` is one large table, accidental repeated extraction is harder to distinguish from valid repeated values.
- This page should be reviewed after aggregate-cell suppression and region hierarchy fixes are added.

**Likely cause**

- The page contains multiple logical sections inside one large bordered form.
- The current normalizer preserves the full detected table as a single grid.
- Section context is not explicitly modeled beyond row/cell text.

**Fix direction**

- After implementing parent/child table hierarchy cleanup, re-check page 5.
- Consider splitting large form tables by section headers:
  - `Cycle Time Details`
  - `BEFORE AFM MACHINING ASSEMBLY`
  - `BEFORE AFM MACHINING`
  - `TOTAL ASSY INVESTMENTS`
- Add section metadata to table rows or split logical sub-tables if that is easier for frontend rendering.

---

### 2. Footer/Approval Text Is Garbled Near The Bottom

**PDF location**

- Page 5 footer area
- Prepared/approved/classification area

**Expected behavior**

- Footer and approval text should be cleanly separated from the table.

**Current JSON behavior**

- `p5_t1` row 56 contains garbled footer-like text:

```json
"text": "oEnA: C/ oKnVfiGdential JR\nPrepared by Approved by"
```

**Problem**

- Footer/classification text is mixed into the table extraction.
- The text appears interleaved/garbled in a similar way to the page 1 footer issue.

**Likely cause**

- The table bbox extends into the footer area.
- Overlapping footer text is grouped with the table cells.

**Fix direction**

- Apply the same footer/header isolation strategy planned for page 1.
- Exclude repeated footer bands from table normalization where possible.
- Preserve footer content separately as page metadata.

## Page 6 Issues

### 1. Casting Remarks Block Is Both Aggregated And Separately Extracted

**PDF location**

- Page 6
- `RFQ REMARKS`
- `Casting Remarks:` section
- Highlighted remarks block containing:
  - `Product design changes required.`
  - `Casting weight given in the drawing, Machining weight extracted from 3d.`
  - `Average wall thcikness 5.0 mm.`
  - `Heat treament basket in -house 50 Nos`
  - AFM process note and numbered pricing factors

**Expected behavior**

- The remarks block should be represented once in a clean structured form.
- Since this is a remarks/narrative region, acceptable frontend shapes could be:
  - one logical remarks section with paragraphs/list items, or
  - a single-column remarks table with separate rows for each note.
- The same content should not appear both as a large parent cell and as separate child rows.

**Current JSON behavior**

- `samples/response.json` has three page 6 tables:
  - `p6_t1`
  - `p6_t2`
  - `p6_t3`
- `p6_t1` row 8 contains the full remarks section as one aggregate cell:

```json
"text": "Casting Remarks:\nProduct design changes required.\nCasting weight given in the drawing, Machining weight extracted from 3d.\nAverage wall thcikness 5.0 mm.\nHeat treament basket in -house 50 Nos\nAs per the design input, we have determined that the AFM process is not required for this part. Instead, we will incorporate the following\nfactors into our pricing:\n1. Special sand core cost : Rs. 110/kg\n2. New hydraulic core shooting process\n3. Dedicated trolloy for sand core movement.\n4. Special care and handling for core testing\nPlease refer to the email below fro design reference."
```

- `p6_t2` separately extracts the same content into individual rows:
  - row 0: `Product design changes required.`
  - row 2: `Average wall thcikness 5.0 mm.\nHeat treament basket in -house 50 Nos`
  - row 3: AFM process paragraph, numbered items, and email reference note

**Problem**

- This is the same parent/child duplication pattern seen on the machining page.
- The parent table keeps the full remarks block as one aggregate cell.
- A child table also extracts the remarks into more useful row-level content.
- The frontend may render duplicate remarks unless the parent aggregate cell is suppressed or the child table is preferred.

**Likely cause**

- The remarks page has a large bordered/highlighted region inside the broader page table.
- Current extraction accepts both the parent page-level table and the child remarks-region table.
- There is no hierarchy/overlap resolver to decide which table should own the text.

**Fix direction**

- Reuse the planned parent/child table-region hierarchy logic.
- Prefer the child remarks table (`p6_t2`) over the aggregate cell inside `p6_t1`.
- Consider a separate response type for narrative sections, because this content is not a typical grid table.
- Add warning code `narrative_region_detected` if remarks blocks are emitted outside normal table grids.

## Page 7 Issues

No extraction issues noted during manual review. Page 7 currently looks acceptable.

## Cross-Page Patterns To Watch

These page 1 issues are expected to repeat on other pages:

- Rotated/vertical text may be reversed.
- Visually merged cells may lose shared values.
- Large table detections may combine multiple logical sub-tables.
- Footer/header text may be included inside table output.
- Overlapping text lines may collapse into unreadable strings.
- Aggregate cells may duplicate data that is also available as detailed row/cell extractions.
- Adjacent side-by-side tables may be merged into one large text block.
- Vertically stacked fragments may need to be merged into one logical table.
- Image-heavy regions may require OCR or a vision model to extract embedded markings/text.
- Non-table vector text near images may need a page-elements response, not just table JSON.
- Narrative/remarks regions may need section output instead of being forced into grid tables.

## Candidate Fix Backlog

1. Add vertical text normalization for rotated labels.
2. Improve rowspan/colspan inference using cell bounding boxes and row/column bands.
3. Split large detected tables into logical sub-tables using section headers and whitespace/border gaps.
4. Add duplicate aggregate-cell suppression when detailed row-level cells are also present.
5. Detect and isolate repeated headers/footers before returning frontend table JSON.
6. Add table-region hierarchy handling for parent/child and side-by-side table detections.
7. Add optional page-level non-table text elements for image/process pages.
8. Plan OCR or vision-model extraction for image-heavy regions.
9. Add narrative/remarks section handling for large paragraph/list blocks.
10. Add logical merge handling for vertically stacked table fragments.
11. Add extraction warnings for:
   - `rotated_text_detected`
   - `span_inferred`
   - `large_aggregate_cell`
   - `footer_overlap_detected`
   - `table_region_may_include_footer`
   - `duplicate_aggregate_cell_suppressed`
   - `nested_table_region_detected`
   - `image_region_not_ocr_processed`
   - `narrative_region_detected`
   - `stacked_table_merged`
