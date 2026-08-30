#!/usr/bin/env python3
"""RF Finder voice-assistant entry point.

The current provider is console-based so the project can be tested without
microphone/cloud credentials. Speech providers can implement SpeechInput and
SpeechOutput later without changing the assistant/router/tool layers.
"""

import sys

from app.assistant import CommandRouter, RFAssistant
from app.assistant.assistant import ConsoleSpeechInput, ConsoleSpeechOutput
from app.assistant.tools import ToolRegistry, register_default_tools
from app.auth import AuthManager, first_run_setup, login_prompt
from app.config import default_config
from app.sources.simulator import SignalSimulator


def main() -> int:
    auth = AuthManager()
    if not auth.has_account():
        first_run_setup(auth)
    session = login_prompt(auth)

    simulator = SignalSimulator(default_config)
    permissions = {"rf.scan", "rf.read"} if session.user.role in {"user", "admin"} else set()
    registry = ToolRegistry(permissions)
    register_default_tools(registry, simulator)
    router = CommandRouter(registry)
    assistant = RFAssistant(router, ConsoleSpeechInput(), ConsoleSpeechOutput())

    print("\nRF Finder Assistant")
    print("Type a command. Type 'help' for commands or 'quit' to exit.\n")
    try:
        while True:
            command = input("You: ").strip()
            if command.lower() in {"quit", "exit"}:
                break
            if command:
                result = router.process(command, assistant.context)
                assistant.context.last_result = result
                print(f"RF Finder: {result['message']}")
    except (KeyboardInterrupt, EOFError):
        print()
    finally:
        if getattr(simulator, "running", False):
            simulator.stop()
        auth.logout(session.token)

    return 0


if __name__ == "__main__":
    sys.exit(main())
