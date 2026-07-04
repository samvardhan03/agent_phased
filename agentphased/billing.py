"""
agentphased.billing -- SaaS paywall stubs.

Provides:
- Tier definitions and usage limits.
- A ``require_tier`` decorator for gating functionality.
- A mock Stripe checkout session generator.
"""

from __future__ import annotations

import functools
import uuid
from typing import Any, Callable, Dict, Sequence


# -- Tier definitions --------------------------------------------------------

TIER_LIMITS: Dict[str, Dict[str, int]] = {
    "free": {
        "max_memory_entries": 1000,
        "max_tools": 3,
        "max_tokens_per_day": 100,
    },
    "pro": {
        "max_memory_entries": 50_000,
        "max_tools": 25,
        "max_tokens_per_day": 10_000,
    },
    "enterprise": {
        "max_memory_entries": -1,   # unlimited
        "max_tools": -1,
        "max_tokens_per_day": -1,
    },
}


def get_tier_limits(tier: str) -> Dict[str, int]:
    """Return the limit dict for *tier*, defaulting to free."""
    return TIER_LIMITS.get(tier, TIER_LIMITS["free"])


# -- require_tier decorator --------------------------------------------------

class TierError(Exception):
    """Raised when an operation is blocked by the agent's subscription tier."""


def require_tier(*allowed_tiers: str) -> Callable:
    """Decorator that restricts a method to agents on one of *allowed_tiers*.

    The decorated function's first positional argument must be an object
    with a ``.tier`` attribute (i.e. an ``Agent`` instance or similar).

    Usage::

        @require_tier("pro", "enterprise")
        def export_full_history(agent, path):
            ...
    """
    def decorator(fn: Callable) -> Callable:
        @functools.wraps(fn)
        def wrapper(agent_or_self: Any, *args: Any, **kwargs: Any) -> Any:
            tier = getattr(agent_or_self, "tier", "free")
            if tier not in allowed_tiers:
                raise TierError(
                    f"Operation '{fn.__name__}' requires tier "
                    f"{', '.join(allowed_tiers)}; current tier is '{tier}'."
                )
            return fn(agent_or_self, *args, **kwargs)
        return wrapper
    return decorator


# -- Mock Stripe checkout ----------------------------------------------------

def mock_stripe_checkout(tier: str, agent_fingerprint: str) -> Dict[str, str]:
    """Return a dummy Stripe checkout session dict.

    In a real deployment this would call the Stripe API and return a
    redirect URL.  Here it returns a deterministic fake URL for testing.
    """
    session_id = uuid.uuid4().hex[:16]
    return {
        "session_id": f"cs_test_{session_id}",
        "url": f"https://checkout.stripe.com/pay/cs_test_{session_id}",
        "tier": tier,
        "agent_fingerprint": agent_fingerprint,
        "status": "open",
    }
