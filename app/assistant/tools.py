"""Controlled tool boundary between the assistant and RF Finder services."""

from dataclasses import dataclass
from typing import Any, Callable


@dataclass(frozen=True)
class Tool:
    name: str
    permission: str
    handler: Callable[..., dict[str, Any]]


class ToolRegistry:
    def __init__(self, permissions: set[str] | None = None):
        self._tools: dict[str, Tool] = {}
        self._permissions = permissions or set()

    def register(self, name: str, permission: str, handler: Callable[..., dict[str, Any]]) -> None:
        if name in self._tools:
            raise ValueError(f"Tool already registered: {name}")
        self._tools[name] = Tool(name, permission, handler)

    def execute(self, name: str, **arguments: Any) -> dict[str, Any]:
        tool = self._tools.get(name)
        if tool is None:
            raise ValueError("Unknown assistant tool")
        if tool.permission and tool.permission not in self._permissions:
            raise PermissionError("Not authorized for this RF Finder operation")
        return tool.handler(**arguments)

    def names(self) -> tuple[str, ...]:
        return tuple(sorted(self._tools))


def register_default_tools(registry: ToolRegistry, rf_engine: Any, detector: Any = None) -> None:
    registry.register("start_scan", "rf.scan", lambda: _start(rf_engine))
    registry.register("stop_scan", "rf.scan", lambda: _stop(rf_engine))
    registry.register("get_status", "rf.read", lambda: _status(rf_engine))
    if detector is not None:
        registry.register("get_signals", "rf.read", lambda: {"signals": detector.current_signals()})


def _start(engine: Any) -> dict[str, Any]:
    engine.start()
    return {"success": True, "message": "RF scan started."}


def _stop(engine: Any) -> dict[str, Any]:
    engine.stop()
    return {"success": True, "message": "RF scan stopped."}


def _status(engine: Any) -> dict[str, Any]:
    status = engine.status() if hasattr(engine, "status") else {"active": True}
    return {"success": True, "status": status}
