from abc import ABC, abstractmethod
from collections.abc import Iterator


class BaseLLMProvider(ABC):
    def __init__(self, model: str, temperature: float = 0.7):
        self.model = model
        self.temperature = temperature

    @abstractmethod
    def chat(self, prompt: str) -> str:
        raise NotImplementedError

    @abstractmethod
    def chat_stream(self, prompt: str) -> Iterator[str]:
        raise NotImplementedError
