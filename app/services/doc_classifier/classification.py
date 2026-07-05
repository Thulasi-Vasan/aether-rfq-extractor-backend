import base64
import json
from pathlib import Path
from typing import Literal

import boto3
import fitz

from app.core.config import get_settings
from app.models import ClassificationCategory, ClassificationResponse
from app.services.doc_classifier.cad_renderer import CADRendererService
from app.core.prompts import get_pdf_classification_prompt, get_cad_classification_prompt

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

        return self._invoke_bedrock(base64_image, prompt)

    def _render_pdf_to_base64_png(self, pdf_path: Path) -> str:
        doc = fitz.open(str(pdf_path))
        page = doc.load_page(0)
        pix = page.get_pixmap(dpi=150)
        png_data = pix.tobytes("png")
        return base64.b64encode(png_data).decode("utf-8")

    def _get_pdf_prompt(self) -> str:
        return get_pdf_classification_prompt()

    def _get_cad_prompt(self) -> str:
        return get_cad_classification_prompt()

    def _invoke_bedrock(self, base64_image: str, prompt: str) -> dict:
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

        return result

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

        result = self._invoke_bedrock(base64_image, prompt)

        category_str = result.get('category')
        try:
            category = ClassificationCategory(category_str)
        except ValueError:
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


class BatchClassificationService:
    def __init__(self):
        self.vlm = VLMClassificationService()

    def classify_batch(self, files: list[Path]) -> list[ClassificationResponse]:
        pdf_files = [f for f in files if f.suffix.lower() == ".pdf" and not f.name.startswith("._")]
        step_files = [f for f in files if f.suffix.lower() in {".step", ".stp"} and not f.name.startswith("._")]

        from app.core.prompts import get_pdf_classification_prompt, get_cad_classification_prompt
        
        results = []
        pdf_results = {}
        
        for pdf in pdf_files:
            try:
                base64_image = self.vlm._render_pdf_to_base64_png(pdf)
                prompt = get_pdf_classification_prompt()
                result = self.vlm._invoke_bedrock(base64_image, prompt)
                
                cat_str = result.get("category", "Unclassified")
                mapped_cat = ClassificationCategory.unclassified
                if cat_str == "Casting": mapped_cat = ClassificationCategory.casting
                elif cat_str == "Machining": mapped_cat = ClassificationCategory.machining
                elif cat_str == "Assembly": mapped_cat = ClassificationCategory.assembly
                
                resp = ClassificationResponse(
                    filename=pdf.name,
                    category=mapped_cat,
                    confidence=float(result.get("confidence", 0.0)),
                    reasoning=result.get("reasoning", "")
                )
                pdf_results[pdf.name] = resp
                results.append(resp)
            except Exception as e:
                print(f"Failed to classify {pdf.name}: {e}")
                resp = ClassificationResponse(
                    filename=pdf.name,
                    category=ClassificationCategory.unclassified,
                    confidence=0.0,
                    reasoning=f"Error: {e}"
                )
                pdf_results[pdf.name] = resp
                results.append(resp)

        for step in step_files:
            try:
                # 1. Direct filename correlation (if STP stem is in PDF stem or vice versa)
                step_stem = step.stem.lower()
                matched_resp = None
                for pdf_name, resp in pdf_results.items():
                    pdf_stem = Path(pdf_name).stem.lower()
                    if step_stem in pdf_stem or pdf_stem in step_stem:
                        matched_resp = resp
                        break
                
                if matched_resp:
                    # Inherit PDF classification
                    results.append(ClassificationResponse(
                        filename=step.name,
                        category=matched_resp.category,
                        confidence=0.9,
                        reasoning="Inherited classification from matching PDF document."
                    ))
                else:
                    base64_image = CADRendererService.render_step_to_base64_png(step)
                    prompt = get_cad_classification_prompt()
                    result = self.vlm._invoke_bedrock(base64_image, prompt)
                    
                    cat_str = result.get("category", "Unclassified")
                    mapped_cat = ClassificationCategory.unclassified
                    if cat_str == "Casting": mapped_cat = ClassificationCategory.casting
                    elif cat_str == "Machining": mapped_cat = ClassificationCategory.machining
                    elif cat_str == "Assembly": mapped_cat = ClassificationCategory.assembly
                    
                    results.append(ClassificationResponse(
                        filename=step.name,
                        category=mapped_cat,
                        confidence=float(result.get("confidence", 0.0)),
                        reasoning=result.get("reasoning", "")
                    ))
            except Exception as e:
                print(f"Failed to classify {step.name}: {e}")
                results.append(ClassificationResponse(
                    filename=step.name,
                    category=ClassificationCategory.unclassified,
                    confidence=0.0,
                    reasoning=f"Error: {e}"
                ))

        return results
