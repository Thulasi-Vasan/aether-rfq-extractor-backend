import base64
import json
from pathlib import Path
from typing import Literal

import boto3
import fitz

from app.core.config import get_settings
from app.models import ClassificationCategory, ClassificationResponse
from app.services.doc_classifier.cad_renderer import CADRendererService


class VLMClassificationService:
    def __init__(self):
        self.settings = get_settings()
        self.bedrock_client = boto3.client(
            "bedrock-runtime",
            region_name=self.settings.bedrock_region,
        )
        self.model_id = self.settings.bedrock_model_id

    def classify_file(self, file_path: Path, filename: str) -> ClassificationResponse:
        ext = file_path.suffix.lower()
        if ext == ".pdf":
            base64_image = self._render_pdf_to_base64_png(file_path)
            prompt = self._get_pdf_prompt()
        elif ext in {".step", ".stp"}:
            base64_image = CADRendererService.render_step_to_base64_png(file_path)
            prompt = self._get_cad_prompt()
        else:
            raise ValueError(f"Unsupported file extension: {ext}")

        return self._invoke_bedrock(filename, base64_image, prompt)

    def _render_pdf_to_base64_png(self, pdf_path: Path) -> str:
        doc = fitz.open(str(pdf_path))
        page = doc.load_page(0)
        pix = page.get_pixmap(dpi=150)
        png_data = pix.tobytes("png")
        return base64.b64encode(png_data).decode("utf-8")

    def _get_pdf_prompt(self) -> str:
        return (
            "You are an expert manufacturing engineer classifying documents. Analyze the attached document page.\n"
            "Categorize the document into EXACTLY ONE of these four categories: 'Casting', 'Machining', 'Assembly', or 'Unclassified'.\n\n"
            "CRITICAL RULE FOR 'Unclassified':\n"
            "If the document contains a commercial RFQ, a standards sheet, a RFQ estimate, a pricing sheet, a cost estimate, a, an invoice, a spreadsheet printout, or if it primarily consists of text and tables WITHOUT a central 2D/3D engineering schematic of a physical part, you MUST categorize it as 'Unclassified'. DO NOT confuse a table/pricing list in an RFQ with a Bill of Materials (BOM) in an Assembly drawing.\n\n"
            "Visual Cues for Engineering Drawings ONLY:\n"
            "- Assembly: An engineering blueprint containing BOTH a schematic of assembled parts AND a BOM/Parts List, or exploded views.\n"
            "- Casting: An engineering blueprint with notes regarding 'Draft Angle', 'Unspecified Radii', 'Shrinkage', or showing organic geometries.\n"
            "- Machining: An engineering blueprint showing precise cross-sections and extensive geometric dimensioning and tolerancing (GD&T) frames.\n\n"
            "Return the result as a JSON object with three keys: 'category' (string: 'Casting', 'Machining', 'Assembly', or 'Unclassified'), "
            "'confidence' (float between 0 and 1), and 'reasoning' (string explaining the cues found)."
        )

    def _get_cad_prompt(self) -> str:
        return (
            "You are an expert manufacturing engineer. Analyze the attached 2D render of a 3D CAD model. "
            "Categorize the part into exactly one of these four categories: 'Casting', 'Machining', 'Assembly', or 'Unclassified'.\n\n"
            "Visual Cues:\n"
            "- Assembly: Look for distinct nested structures, multiple visually separated components, or fasteners.\n"
            "- Casting: Look for organic B-spline surfaces, fillets everywhere, smooth transitions, parting lines.\n"
            "- Machining: Look for sharp edges, planar faces, threaded holes, cylindrical features indicating subtractive manufacturing.\n"
            "- Unclassified: If it does not appear to be an engineering model of these types.\n\n"
            "Return the result as a JSON object with three keys: 'category' (string: 'Casting', 'Machining', 'Assembly', or 'Unclassified'), "
            "'confidence' (float between 0 and 1), and 'reasoning' (string explaining the cues found)."
        )

    def _invoke_bedrock(self, filename: str, base64_image: str, prompt: str) -> ClassificationResponse:
        messages = [
            {
                "role": "user",
                "content": [
                    {
                        "image": {
                            "format": "png",
                            "source": {
                                "bytes": base64.b64decode(base64_image)
                            }
                        }
                    },
                    {
                        "text": prompt
                    }
                ]
            }
        ]

        response = self.bedrock_client.converse(
            modelId=self.model_id,
            messages=messages,
            inferenceConfig={
                "maxTokens": 1024,
                "temperature": 0.0,
            }
        )

        # The converse API returns text in response['output']['message']['content'][0]['text']
        content = response.get('output', {}).get('message', {}).get('content', [])[0].get('text', '')

        # Attempt to parse JSON from the text block
        # The model might output conversational text around the JSON, so we strip it.
        try:
            start_idx = content.find('{')
            end_idx = content.rfind('}') + 1
            json_str = content[start_idx:end_idx]
            result = json.loads(json_str)
        except Exception:
            # Fallback if json parsing fails completely
            raise ValueError(f"Failed to parse model output as JSON. Output was: {content}")

        category_str = result.get('category')
        try:
            category = ClassificationCategory(category_str)
        except ValueError:
            # Coerce mapping if the model capitalized differently
            mapped = {'casting': ClassificationCategory.casting,
                      'machining': ClassificationCategory.machining,
                      'assembly': ClassificationCategory.assembly,
                      'unclassified': ClassificationCategory.unclassified}
            category = mapped.get(str(category_str).lower(), ClassificationCategory.unclassified)

        return ClassificationResponse(
            filename=filename,
            category=category,
            confidence=float(result.get('confidence', 0.0)),
            reasoning=result.get('reasoning', '')
        )
