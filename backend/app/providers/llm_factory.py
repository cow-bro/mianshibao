from app.core.config import get_settings
from app.providers.llm.base import BaseLLMProvider
from app.providers.llm.fallback_provider import FallbackProvider
from app.providers.llm.qwen_provider import QwenProvider


class LLMService:
    def __init__(self) -> None:
        self.settings = get_settings()

    def get_provider(self, scenario: str) -> BaseLLMProvider:
        scenario_key = scenario.upper()
        config = self.settings.llm_scenario_configs.get(
            scenario_key, self.settings.llm_scenario_configs["DEFAULT"]
        )
        provider_name = str(config.get("provider", "fallback")).lower()
        model = str(config.get("model", "fallback"))
        temperature = float(config.get("temperature", 0.5))

        if provider_name == "qwen":
            return QwenProvider(model=model, temperature=temperature)
        return FallbackProvider(model=model, temperature=temperature)

    def chat(self, scenario: str, prompt: str) -> str:
        provider = self.get_provider(scenario)
        return provider.chat(prompt)

    def chat_stream(self, scenario: str, prompt: str):
        provider = self.get_provider(scenario)
        return provider.chat_stream(prompt)


def get_llm_provider(scene: str = "DEFAULT") -> BaseLLMProvider:
    return LLMService().get_provider(scene)
