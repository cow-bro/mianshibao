from app.providers.llm_factory import LLMService


class AIProvider:
    def __init__(self) -> None:
        self.llm_service = LLMService()

    def chat(self, prompt: str, scenario: str = "DEFAULT") -> str:
        return self.llm_service.chat(scenario=scenario, prompt=prompt)
