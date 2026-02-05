from abc import ABC, abstractmethod
import os
from typing import Optional, List, Dict

class LLMProvider(ABC):
    @abstractmethod
    def generate(self, prompt: str, system_prompt: Optional[str] = None, max_tokens: int = 1000) -> str:
        """Generate text from the LLM"""
        pass

class MockProvider(LLMProvider):
    def generate(self, prompt: str, system_prompt: Optional[str] = None, max_tokens: int = 1000) -> str:
        return f"[MOCK RESPOSE] System: {system_prompt} | User: {prompt[:50]}..."

class OpenAIProvider(LLMProvider):
    def __init__(self, api_key: str, model: str = "gpt-4"):
        try:
            from openai import OpenAI
            self.client = OpenAI(api_key=api_key)
            self.model = model
        except ImportError:
            raise ImportError("openai package not installed")

    def generate(self, prompt: str, system_prompt: Optional[str] = None, max_tokens: int = 1000) -> str:
        messages = []
        if system_prompt:
            messages.append({"role": "system", "content": system_prompt})
        messages.append({"role": "user", "content": prompt})

        response = self.client.chat.completions.create(
            model=self.model,
            messages=messages,
            max_tokens=max_tokens
        )
        return response.choices[0].message.content

class AnthropicProvider(LLMProvider):
    def __init__(self, api_key: str, model: str = "claude-3-opus-20240229"):
        try:
            import anthropic
            self.client = anthropic.Anthropic(api_key=api_key)
            self.model = model
        except ImportError:
            raise ImportError("anthropic package not installed")

    def generate(self, prompt: str, system_prompt: Optional[str] = None, max_tokens: int = 1000) -> str:
        # Anthropic uses a system parameter, not a message role for system
        response = self.client.messages.create(
            model=self.model,
            max_tokens=max_tokens,
            system=system_prompt,
            messages=[{"role": "user", "content": prompt}]
        )
        return response.content[0].text

def get_provider() -> LLMProvider:
    """Factory to get the configured provider"""
    provider_type = os.environ.get("LLM_PROVIDER", "mock").lower()
    
    if provider_type == "openai":
        return OpenAIProvider(os.environ.get("OPENAI_API_KEY"))
    elif provider_type == "anthropic":
        return AnthropicProvider(os.environ.get("ANTHROPIC_API_KEY"))
    else:
        return MockProvider()
