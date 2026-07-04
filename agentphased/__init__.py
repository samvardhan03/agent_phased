"""
agentphased -- Unified agentic platform.

Glues AgentID (cryptographic identity), AgentMem (persistent memory),
and Agentool (API schema inference / tool execution) into a single
coherent ``Agent`` object.
"""

from __future__ import annotations

__version__ = "0.1.0"

from typing import Any, Optional

from agentid import AgentIdentity
from agentmem import Memory

from agentphased.billing import TIER_LIMITS, TierError, get_tier_limits
from agentphased.bus import EventBus
from agentphased._tool_registry import ToolRegistry


class Agent:
    """Unified agent combining identity, memory, tools, and an event bus.

    Parameters
    ----------
    name : str
        Human-readable agent name (passed to AgentIdentity).
    project : str
        Project namespace (passed to AgentIdentity).
    billing : bool
        When True, enforce usage limits based on *tier*.
    tier : str
        Subscription tier: ``"free"``, ``"pro"``, or ``"enterprise"``.
    db_path : str or None
        Override the RocksDB path for AgentMem (default: ~/.agentmem/db).
    """

    def __init__(
        self,
        name: str,
        project: str,
        *,
        billing: bool = False,
        tier: str = "free",
        db_path: Optional[str] = None,
    ) -> None:
        # -- 1. Cryptographic identity --------------------------------------
        self.identity: AgentIdentity = AgentIdentity(name=name, project=project)

        # -- 2. Persistent memory (namespace = fingerprint) -----------------
        mem_kwargs: dict = {"namespace": self.identity.fingerprint}
        if db_path is not None:
            mem_kwargs["db_path"] = db_path
        self.memory: Memory = Memory(**mem_kwargs)

        # -- 3. Event bus ---------------------------------------------------
        self.bus: EventBus = EventBus()

        # -- 4. Tool registry -----------------------------------------------
        self.tools: ToolRegistry = ToolRegistry(
            identity=self.identity,
            memory=self.memory,
            bus=self.bus,
        )

        # -- 5. Default subscriber: tool.called -> episodic log -------------
        self.bus.subscribe("tool.called", self._log_tool_event)

        # -- 6. Billing -----------------------------------------------------
        self._billing: bool = billing
        self._tier: str = tier
        if billing:
            self._enforce_tier(tier)

    # -- properties ----------------------------------------------------------

    @property
    def fingerprint(self) -> str:
        return self.identity.fingerprint

    @property
    def name(self) -> str:
        return self.identity.name

    @property
    def project(self) -> str:
        return self.identity.project

    @property
    def tier(self) -> str:
        return self._tier

    # -- internal ------------------------------------------------------------

    def _log_tool_event(self, event: dict) -> None:
        """Default bus subscriber: persist tool calls as episodic memory."""
        url = event.get("url", "unknown")
        method = event.get("method", "unknown")
        error = event.get("error")
        if error:
            summary = f"Error: {error}"
        else:
            raw = event.get("result")
            summary = str(raw)[:200] if raw is not None else "no result"
        try:
            self.memory.log_episode(
                action=f"tool.called {url} {method}",
                result_summary=summary,
            )
        except Exception:
            pass

    def _enforce_tier(self, tier: str) -> None:
        """Apply tier-based limits. Called once during __init__."""
        limits = get_tier_limits(tier)
        self._max_memory_entries = limits["max_memory_entries"]
        self._max_tools = limits["max_tools"]


__all__ = [
    "__version__",
    "Agent",
    "EventBus",
    "ToolRegistry",
    "TierError",
]
