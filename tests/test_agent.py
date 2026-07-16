"""
End-to-end tests for the agentphased unified Agent.

All tests run fully isolated -- no network calls, no real Rust native
modules.  We mock the native layer where necessary.
"""

import json
import os
import pytest
from unittest.mock import MagicMock, patch, PropertyMock

from agentphased import Agent, EventBus, TierError
from agentphased.bus import EventBus as EventBusClass
from agentphased.billing import require_tier, mock_stripe_checkout, get_tier_limits

try:
    from agentmem import _native
    HAS_NATIVE = True
except ImportError:
    HAS_NATIVE = False


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

DUMMY_SPEC = os.path.join(os.path.dirname(__file__), "dummy_spec.json")


@pytest.fixture(autouse=True)
def _write_dummy_spec(tmp_path):
    """Write a minimal OpenAPI spec for tool tests."""
    spec = {
        "openapi": "3.0.0",
        "info": {"title": "Test API", "version": "0.1.0"},
        "servers": [{"url": "https://test.example.com"}],
        "paths": {
            "/ping": {
                "get": {
                    "summary": "Ping",
                    "operationId": "ping",
                    "parameters": [],
                    "responses": {"200": {"description": "OK"}},
                }
            }
        },
    }
    path = tmp_path / "dummy_spec.json"
    path.write_text(json.dumps(spec))
    # Patch the global so tests can reference it
    global DUMMY_SPEC
    DUMMY_SPEC = f"file://{path}"


@pytest.fixture
def agent(tmp_path):
    """Create an Agent with an isolated memory db."""
    db = str(tmp_path / "testdb")
    return Agent("test-agent", "test-project", db_path=db)


@pytest.fixture
def billing_agent(tmp_path):
    """Create a free-tier billing Agent."""
    db = str(tmp_path / "billingdb")
    return Agent("billing-agent", "billing-project", billing=True, tier="free", db_path=db)


# ---------------------------------------------------------------------------
# Test 1: Initialization wires all three sub-modules correctly
# ---------------------------------------------------------------------------

class TestInitialization:
    def test_identity_is_wired(self, agent):
        assert agent.identity is not None
        assert agent.name == "test-agent"
        assert agent.project == "test-project"
        assert agent.fingerprint.startswith("ag:sha256:")

    def test_memory_is_wired(self, agent):
        assert agent.memory is not None
        assert agent.memory.namespace == agent.fingerprint

    def test_tools_is_wired(self, agent):
        assert agent.tools is not None
        assert agent.tools.list() == []

    def test_bus_is_wired(self, agent):
        assert agent.bus is not None
        assert isinstance(agent.bus, EventBusClass)

    def test_deterministic_identity(self, tmp_path):
        """Same (name, project) produces the same fingerprint."""
        db1 = str(tmp_path / "db1")
        db2 = str(tmp_path / "db2")
        a1 = Agent("same", "same", db_path=db1)
        a2 = Agent("same", "same", db_path=db2)
        assert a1.fingerprint == a2.fingerprint


# ---------------------------------------------------------------------------
# Test 2: Adding a tool triggers an identity check
# ---------------------------------------------------------------------------

class TestToolIdentityWiring:
    def test_add_tool_passes_identity(self, agent):
        """tool.add() should create an agentool.Tool with the agent's identity."""
        tool = agent.tools.add(DUMMY_SPEC)
        # The Tool constructor received our identity
        assert tool.identity is agent.identity

    def test_add_tool_passes_memory(self, agent):
        """tool.add() should create an agentool.Tool with the agent's memory."""
        tool = agent.tools.add(DUMMY_SPEC)
        assert tool.memory is agent.memory

    def test_add_tool_registers_url(self, agent):
        agent.tools.add(DUMMY_SPEC)
        assert DUMMY_SPEC in agent.tools.list()


# ---------------------------------------------------------------------------
# Test 3: tool.call routes through EventBus -> episodic memory
# ---------------------------------------------------------------------------

class TestToolCallEventRouting:
    def test_call_fires_bus_event(self, agent):
        """tools.call() should publish a tool.called event."""
        tool = agent.tools.add(DUMMY_SPEC)
        # Replace the native schema with a mock so we don't do real HTTP
        mock_schema = MagicMock()
        mock_schema.call_blocking.return_value = '{"status": "ok"}'
        tool._native_schema = mock_schema
        tool._get_identity_credentials = MagicMock(return_value={"type": "bearer", "token": "test"})

        agent.tools.call(DUMMY_SPEC, "ping")

        events = agent.bus.history("tool.called")
        assert len(events) == 1
        assert events[0]["url"] == DUMMY_SPEC
        assert events[0]["method"] == "ping"

    @pytest.mark.skipif(not HAS_NATIVE, reason="Native memory extension not available (ONNX missing)")
    def test_call_logs_to_episodic_memory(self, agent):
        """The default bus subscriber should log the event into memory."""
        tool = agent.tools.add(DUMMY_SPEC)
        mock_schema = MagicMock()
        mock_schema.call_blocking.return_value = '{"status": "ok"}'
        tool._native_schema = mock_schema
        tool._get_identity_credentials = MagicMock(return_value={"type": "bearer", "token": "test"})

        agent.tools.call(DUMMY_SPEC, "ping")

        episodes = agent.memory.episodes(last_n=5)
        assert len(episodes) >= 1
        assert any("tool.called" in e["action"] for e in episodes)
        assert any("ping" in e["action"] for e in episodes)

    def test_call_error_still_fires_event(self, agent):
        """Even if call_blocking raises, an event should still be published."""
        tool = agent.tools.add(DUMMY_SPEC)
        mock_schema = MagicMock()
        mock_schema.call_blocking.side_effect = RuntimeError("network down")
        tool._native_schema = mock_schema
        tool._get_identity_credentials = MagicMock(return_value={"type": "bearer", "token": "test"})

        with pytest.raises(RuntimeError, match="network down"):
            agent.tools.call(DUMMY_SPEC, "ping")

        events = agent.bus.history("tool.called")
        assert len(events) == 1
        assert events[0]["error"] == "network down"


# ---------------------------------------------------------------------------
# Test 4: Billing -- free tier limits
# ---------------------------------------------------------------------------

class TestBilling:
    def test_free_tier_sets_limits(self, billing_agent):
        assert billing_agent.tier == "free"
        assert billing_agent._max_memory_entries == 1000
        assert billing_agent._max_tools == 3

    def test_require_tier_blocks_free(self):
        @require_tier("pro", "enterprise")
        def premium_op(agent):
            return "ok"

        mock_agent = MagicMock()
        mock_agent.tier = "free"
        with pytest.raises(TierError, match="requires tier"):
            premium_op(mock_agent)

    def test_require_tier_allows_pro(self):
        @require_tier("pro", "enterprise")
        def premium_op(agent):
            return "ok"

        mock_agent = MagicMock()
        mock_agent.tier = "pro"
        assert premium_op(mock_agent) == "ok"

    def test_mock_stripe_checkout(self, billing_agent):
        session = mock_stripe_checkout("pro", billing_agent.fingerprint)
        assert session["tier"] == "pro"
        assert session["agent_fingerprint"] == billing_agent.fingerprint
        assert session["url"].startswith("https://checkout.stripe.com/pay/cs_test_")
        assert session["status"] == "open"


# ---------------------------------------------------------------------------
# EventBus unit tests
# ---------------------------------------------------------------------------

class TestEventBus:
    def test_publish_and_subscribe(self):
        bus = EventBusClass()
        received = []
        bus.subscribe("test.topic", lambda e: received.append(e))
        bus.publish("test.topic", {"data": 1})
        assert len(received) == 1
        assert received[0]["data"] == 1
        assert received[0]["topic"] == "test.topic"

    def test_history_filters_by_topic(self):
        bus = EventBusClass()
        bus.publish("a", {"v": 1})
        bus.publish("b", {"v": 2})
        bus.publish("a", {"v": 3})
        assert len(bus.history("a")) == 2
        assert len(bus.history("b")) == 1
        assert len(bus.history()) == 3

    def test_clear(self):
        bus = EventBusClass()
        bus.subscribe("x", lambda e: None)
        bus.publish("x", {})
        bus.clear()
        assert bus.history() == []
