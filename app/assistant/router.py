"""Intent-to-tool routing for RF Finder."""

from .intents import Intent, parse_command
from .tools import ToolRegistry


class CommandRouter:
    def __init__(self, tools: ToolRegistry):
        self.tools = tools

    def process(self, text: str, context) -> dict:
        parsed = parse_command(text)
        context.last_intent = parsed.intent.value

        try:
            if parsed.intent == Intent.START_SCAN:
                result = self.tools.execute("start_scan")
                context.scan_active = True
                return {"success": True, "message": result.get("message", "RF scan started.")}
            if parsed.intent == Intent.STOP_SCAN:
                result = self.tools.execute("stop_scan")
                context.scan_active = False
                return {"success": True, "message": result.get("message", "RF scan stopped.")}
            if parsed.intent == Intent.GET_STATUS:
                result = self.tools.execute("get_status")
                return {"success": True, "message": f"Current RF status: {result.get('status')}."}
            if parsed.intent == Intent.GET_SIGNALS:
                result = self.tools.execute("get_signals")
                count = len(result.get("signals", []))
                return {"success": True, "message": f"There are {count} detected signals.", "data": result}
            if parsed.intent == Intent.HELP:
                return {"success": True, "message": "I can start or stop scans, report status, list detected signals, and save measurements when those tools are enabled."}
            if parsed.intent == Intent.SET_FREQUENCY:
                return {"success": False, "message": "Frequency control is not enabled yet."}
            if parsed.intent == Intent.SAVE_MEASUREMENT:
                return {"success": False, "message": "Measurement storage is not enabled yet."}
            if parsed.intent == Intent.GET_LOCATION:
                return {"success": False, "message": "GPS is not enabled yet."}
            if parsed.intent == Intent.GET_STRONGEST_SIGNAL:
                return {"success": False, "message": "Signal ranking is not enabled yet."}
            return {"success": False, "message": "I did not recognize that RF Finder command."}
        except (PermissionError, ValueError) as exc:
            return {"success": False, "message": str(exc)}
