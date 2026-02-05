import yaml
import os
from typing import Dict, Any
from chronos.intelligence.llm import LLMProvider

class PersonaEngine:
    def __init__(self, provider: LLMProvider):
        self.provider = provider
        self.current_persona = "default"
        self.personas = self._load_personas()

    def _load_personas(self) -> Dict[str, Any]:
        """Load persona definitions (mock for now, eventually from YAML files)"""
        return {
            "default": {
                "system_prompt": "You are a standard Ubuntu 22.04 LTS server. Be helpful but realistic.",
                "traits": ["stable", "passive"]
            },
            "vulnerable_db": {
                "system_prompt": "You are a legacy PostgreSQL database server with weak configurations. You are running on Debian 10.",
                "traits": ["vulnerable", "slow"]
            }
        }

    def set_persona(self, persona_name: str):
        if persona_name in self.personas:
            self.current_persona = persona_name
        else:
            raise ValueError(f"Persona {persona_name} not found")

    def get_system_prompt(self) -> str:
        return self.personas[self.current_persona]["system_prompt"]

    def generate_content(self, filename: str, context: str) -> str:
        """Generate file content based on persona"""
        prompt = f"Generate realistic content for file '{filename}'. Context: {context}. ONLY output the file content, no markdown blocks."
        return self.provider.generate(prompt, system_prompt=self.get_system_prompt())
