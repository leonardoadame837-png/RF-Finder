"""Voice assistant orchestration; speech providers are intentionally replaceable."""

from dataclasses import dataclass, field
from typing import Any, Protocol


class SpeechInput(Protocol):
    def listen(self) -> str: ...


class SpeechOutput(Protocol):
    def speak(self, text: str) -> None: ...


@dataclass
class AssistantContext:
    last_intent: str | None = None
    scan_active: bool = False
    last_result: dict[str, Any] = field(default_factory=dict)


class RFAssistant:
    def __init__(self, router, speech_input: SpeechInput, speech_output: SpeechOutput):
        self.router = router
        self.speech_input = speech_input
        self.speech_output = speech_output
        self.context = AssistantContext()

    def run_once(self) -> dict[str, Any] | None:
        text = self.speech_input.listen()
        if not text:
            return None
        result = self.router.process(text, self.context)
        self.context.last_result = result
        self.speech_output.speak(result["message"])
        return result


class ConsoleSpeechInput:
    """Push-to-talk-friendly development provider using stdin."""
    def listen(self) -> str:
        return input("You: ").strip()


class ConsoleSpeechOutput:
    def speak(self, text: str) -> None:
        print(f"RF Finder: {text}")
