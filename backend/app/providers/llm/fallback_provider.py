import random
from collections.abc import Iterator

from app.providers.llm.base import BaseLLMProvider


class FallbackProvider(BaseLLMProvider):
    CANNED_RESPONSES = [
        "System is busy. Please retry in a moment.",
        "Received your request. Returning fallback response for stability.",
        "Temporary degraded mode is active. Keep prompts concise for better results.",
    ]

    def chat(self, prompt: str) -> str:
        if not prompt.strip():
            return random.choice(self.CANNED_RESPONSES)
        return f"[fallback:{self.model}] {random.choice(self.CANNED_RESPONSES)} Prompt={prompt[:200]}"

    def chat_stream(self, prompt: str) -> Iterator[str]:
        response = self.chat(prompt)
        chunk_size = 24
        for i in range(0, len(response), chunk_size):
            yield response[i : i + chunk_size]
