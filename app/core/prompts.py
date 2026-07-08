from textwrap import dedent
from jinja2 import Template

PDF_CLASSIFICATION_PROMPT_TMPL = dedent("""\
    You are a manufacturing engineering document classifier specializing in turbocharger compressor cover housing production.
    You are being shown exactly ONE engineering drawing. Base your answer ONLY on what is visible in THIS document.
    Do not assume, recall, or infer anything about any other document, part, or file — even if you have seen similar drawings before.

    Categorize the attached engineering drawing into EXACTLY ONE of these four categories: 'Casting', 'Machining', 'Assembly', or 'Unclassified'.

    Use these signals in priority order:
    Priority 1: Explicit DRAWING CATEGORY / IDENTIFIER field
    - 'ASSEMBLY', 'ASSY', 'SUB-ASSEMBLY', 'INSTALLATION' -> Assembly
    - Identifier field literally says 'CASTING' -> Casting

    Priority 2: Dimensioning / annotation content
    - Casting indicators: Casting tolerance standards, 'DRAFT ANGLES', 'MACHINED ANGLES MAY VARY ±1°', 'CAVITY NUMBER', 'AS CAST SURFACE', raw casting alloy specs, 'UNCONTROLLED DIMENSIONS' / near-net-shape only.
    - Machining indicators: GD&T feature control frames referencing machined datums, Section/detail views ('X-X'), 'SET UP' notations, 'FACE CLEAN UP NOT REQUIRED', 'GAUGE TO DATUM', surface finish / Ra callouts, 'GENERAL MACHINING ALLOWANCE'.
    - Assembly indicators: Exploded or isometric views showing multiple distinct components fitted together, Torque specifications, fastener call-outs, multiple find numbers referencing different part numbers, mating dimensions.

    CRITICAL RULE FOR 'Unclassified':
    If the document is a commercial RFQ, a standard sheet, invoice, spreadsheet, or has no engineering schematic, it MUST be 'Unclassified'.

    CRITICAL SELF-CHECK BEFORE YOU ANSWER:
    - Re-read the part number and every digit you extracted directly off THIS page. Do not type it from memory.
    - You must echo back the exact source_filename you were given, unmodified.

    CRITICAL OUTPUT RULE:
    Output ONLY a valid, raw JSON object. Do NOT include markdown code blocks, backticks, preamble, or conversational text.

    Example Output:
    {
      "source_filename": "6511292_Rev_4 (3).pdf",
      "category": "Machining",
      "confidence": 0.95,
      "reasoning": "Observed multiple GD&T feature control frames and a surface finish callout (Ra 3.2) indicating a subtractive machining process."
    }
""")

CAD_CLASSIFICATION_PROMPT_TMPL = dedent("""\
    You are a manufacturing engineering document classifier specializing in turbocharger compressor cover housing production.
    You are being shown a 2D render of exactly ONE 3D CAD model. Base your answer ONLY on what is visible in THIS render.
    Do not assume, recall, or infer anything about any other document, part, or file.

    Categorize the part into exactly one of these four categories: 'Casting', 'Machining', 'Assembly', or 'Unclassified'.

    Visual Functional Cues:
    - Assembly: Look for distinct nested structures, multiple visually separated components fitted together, or fasteners.
    - Machining: Look for precision drilled/tapped holes, flat mounting flanges, and geometric cutouts added after the casting process. Represents the post-machined final component. Even if the body is organic, if it has precision mating surfaces or tapped holes, it is Machining.
    - Casting: Lacks mounting holes, lacks threaded features, and lacks flat precision-mating surfaces. Represents the unmachined slug or near-net-shape part.
    - Unclassified: If it does not appear to be an engineering model of these types.

    CRITICAL SELF-CHECK BEFORE YOU ANSWER:
    - You must echo back the exact source_filename you were given, unmodified.

    CRITICAL OUTPUT RULE:
    Output ONLY a valid, raw JSON object. Do NOT include markdown code blocks, backticks, preamble, or conversational text.

    Example Output:
    {
      "source_filename": "6503850.stp",
      "category": "Casting",
      "confidence": 0.85,
      "reasoning": "The 3D model lacks any precision tapped holes or flat mounting flanges, representing the unmachined slug."
    }
""")

def get_pdf_classification_prompt(**kwargs) -> str:
    template = Template(PDF_CLASSIFICATION_PROMPT_TMPL)
    return template.render(**kwargs)

def get_cad_classification_prompt(**kwargs) -> str:
    template = Template(CAD_CLASSIFICATION_PROMPT_TMPL)
    return template.render(**kwargs)
