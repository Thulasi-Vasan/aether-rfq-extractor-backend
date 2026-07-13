from enum import Enum
from pydantic import BaseModel

class ClassificationCategory(str, Enum):
    casting = "Casting"
    machining = "Machining"
    assembly = "Assembly"
    unclassified = "Unclassified"


class ClassificationResponse(BaseModel):
    filename: str
    category: ClassificationCategory
    confidence: float
    reasoning: str
