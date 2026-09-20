from enum import Enum
from dataclasses import dataclass
from typing import Dict, Any

class GenerationSource(str, Enum):
    LLM = "llm"
    CACHE = "cache"
    FALLBACK = "fallback"
    TEMPLATE = "template"

@dataclass
class ProvenanceRecord:
    model: str
    generation_source: GenerationSource
    file_class: str
    prompt_version: str
    generated_at: str
    validated: bool
    
    def to_dict(self) -> Dict[str, Any]:
        """Serialize exactly these fields to strings for Redis Hash mapping."""
        return {
            "model": self.model,
            "generation_source": self.generation_source.value,
            "file_class": self.file_class.upper(), # Ensuring ENUM-like casing as requested
            "prompt_version": self.prompt_version,
            "generated_at": self.generated_at,
            "validated": "true" if self.validated else "false"
        }
