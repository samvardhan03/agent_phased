"""
agentphased._tool_registry -- Managed tool collection.

Wraps agentool.Tool instances, wires identity and memory automatically,
and publishes ``tool.called`` events to the EventBus on every invocation.
"""

from __future__ import annotations

import time
from typing import Any, Dict, List, Optional

from agentphased.bus import EventBus


class ToolRegistry:
    """Registry of agentool.Tool instances bound to a single agent."""

    def __init__(
        self,
        identity: Any,
        memory: Any,
        bus: EventBus,
    ) -> None:
        self._identity = identity
        self._memory = memory
        self._bus = bus
        self._tools: Dict[str, Any] = {}

    # -- public API ----------------------------------------------------------

    def add(self, url: str) -> Any:
        """Wrap *url* as an agentool.Tool and register it.

        The Tool is constructed with the agent's identity and memory so
        that credential injection and schema caching work automatically.
        """
        from agentool import Tool

        tool = Tool(url, identity=self._identity, memory=self._memory)
        self._tools[url] = tool
        return tool

    def call(self, url: str, method: str, **kwargs: Any) -> Any:
        """Invoke *method* on the tool registered under *url*.

        Publishes a ``tool.called`` event to the bus after the call
        completes (or fails).
        """
        tool = self._tools.get(url)
        if tool is None:
            raise KeyError(f"No tool registered for '{url}'. Call agent.tools.add(url) first.")

        error: Optional[str] = None
        result: Any = None
        try:
            result = tool.call(method, **kwargs)
        except Exception as exc:
            error = str(exc)
            raise
        finally:
            self._bus.publish("tool.called", {
                "url": url,
                "method": method,
                "params": kwargs,
                "result": result if error is None else None,
                "error": error,
                "ts": time.time(),
            })

        return result

    def list(self) -> List[str]:
        """Return the URLs of all registered tools."""
        return list(self._tools.keys())

    def get(self, url: str) -> Any:
        """Return the Tool instance for *url*, or None."""
        return self._tools.get(url)
