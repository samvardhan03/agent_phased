import asyncio
import json
from contextlib import asynccontextmanager
from typing import AsyncGenerator

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from sse_starlette.sse import EventSourceResponse

from agentphased import Agent


# Global singleton agent for the dashboard
agent = Agent(name="dashboard-agent", project="agentphased")

# Event queue for SSE clients
_subscribers: list[asyncio.Queue] = []


def _on_bus_event(event: dict) -> None:
    """Callback fired synchronously by EventBus.publish()."""
    # We must push to async queues in the running event loop
    loop = None
    try:
        loop = asyncio.get_running_loop()
    except RuntimeError:
        return  # No running event loop

    if loop.is_running():
        # Dispatch to all connected SSE clients
        for queue in _subscribers:
            loop.call_soon_threadsafe(queue.put_nowait, event)


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Subscribe to all events
    # We can subscribe to a specific topic or add a wildcard capability to EventBus.
    # Currently EventBus requires an exact topic. Let's subscribe to 'tool.called' and 'system'
    agent.bus.subscribe("tool.called", _on_bus_event)
    agent.bus.subscribe("system", _on_bus_event)
    yield
    # Cleanup if needed


app = FastAPI(title="AgentPhased API", lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/api/identity")
def get_identity():
    return {
        "name": agent.name,
        "project": agent.project,
        "fingerprint": agent.fingerprint,
        "public_key_hex": agent.identity.public_key_hex,
    }


@app.get("/api/memory/episodes")
def get_episodes(limit: int = 100):
    return agent.memory.episodes(last_n=limit)


@app.get("/api/tools")
def list_tools():
    return agent.tools.list()


from fastapi import HTTPException

@app.post("/api/tools/add")
def add_tool(url: str):
    try:
        agent.tools.add(url)
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))
        
    # Emit a system event so the dashboard knows
    agent.bus.publish("system", {"action": "tool.added", "url": url})
    return {"status": "ok"}


@app.get("/api/events")
async def sse_events():
    """SSE endpoint for real-time bus events."""
    queue = asyncio.Queue()
    _subscribers.append(queue)

    async def event_generator() -> AsyncGenerator[dict, None]:
        try:
            while True:
                # Wait for an event to be put into the queue
                event = await queue.get()
                yield {
                    "event": "message",
                    "data": json.dumps(event)
                }
        except asyncio.CancelledError:
            pass
        finally:
            _subscribers.remove(queue)

    return EventSourceResponse(event_generator())


if __name__ == "__main__":
    import uvicorn
    # Publish a startup event
    agent.bus.publish("system", {"action": "startup", "message": "Backend initialized."})
    uvicorn.run(app, host="127.0.0.1", port=8000)
