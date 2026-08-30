from app.assistant.intents import Intent, parse_command
from app.assistant.router import CommandRouter
from app.assistant.tools import ToolRegistry


class FakeEngine:
    def __init__(self):
        self.started = False

    def start(self):
        self.started = True

    def stop(self):
        self.started = False

    def status(self):
        return {"active": self.started}


def test_parse_scan_command():
    assert parse_command("Start scanning").intent == Intent.START_SCAN


def test_parse_frequency():
    parsed = parse_command("set center frequency to 915 MHz")
    assert parsed.intent == Intent.SET_FREQUENCY
    assert parsed.arguments["frequency_hz"] == 915_000_000


def test_router_enforces_permission():
    engine = FakeEngine()
    tools = ToolRegistry()
    tools.register("start_scan", "rf.scan", lambda: {"message": "started"})
    router = CommandRouter(tools)
    result = router.process("start scan", type("C", (), {})())
    assert result["success"] is False
    assert "authorized" in result["message"]


def test_router_starts_scan():
    engine = FakeEngine()
    tools = ToolRegistry({"rf.scan"})
    tools.register("start_scan", "rf.scan", lambda: engine.start() or {"message": "RF scan started."})
    router = CommandRouter(tools)
    context = type("C", (), {"last_intent": None, "scan_active": False})()
    result = router.process("start scan", context)
    assert result["success"] is True
    assert engine.started is True
    assert context.scan_active is True
