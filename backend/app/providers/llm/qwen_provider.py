from collections.abc import Iterator

from circuitbreaker import circuit
from dashscope import Generation
from tenacity import retry, stop_after_attempt, wait_exponential

from app.core.config import get_settings
from app.providers.llm.base import BaseLLMProvider


class QwenProvider(BaseLLMProvider):
    def __init__(self, model: str, temperature: float = 0.7):
        super().__init__(model=model, temperature=temperature)
        self.settings = get_settings()

    @retry(stop=stop_after_attempt(3), wait=wait_exponential(multiplier=1, min=1, max=8), reraise=True)
    @circuit(failure_threshold=5, recovery_timeout=30)
    def _invoke(self, prompt: str) -> str:
        if not self.settings.dashscope_api_key:
            # Keep local/dev bootstrapping available even without a real API key.
            return f"[qwen-mock:{self.model}] {prompt}"

        resp = Generation.call(
            model=self.model,
            api_key=self.settings.dashscope_api_key,
            temperature=self.temperature,
            result_format="message",
            messages=[{"role": "user", "content": prompt}],
        )
        try:
            return resp.output.choices[0].message.content
        except Exception as exc:
            raise RuntimeError(f"invalid qwen response: {resp}") from exc

    def chat(self, prompt: str) -> str:
        return self._invoke(prompt)

    def chat_stream(self, prompt: str) -> Iterator[str]:
        # DashScope SDK streaming can be wired later; expose iterator contract now.
        response = self.chat(prompt)
        chunk_size = 24
        for i in range(0, len(response), chunk_size):
            yield response[i : i + chunk_size]
