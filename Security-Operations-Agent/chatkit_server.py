from typing import List, Dict, Optional, AsyncIterator, Any
import uuid  # <--- Added import
from agents import Runner
from chatkit.agents import AgentContext, simple_to_agent_input, stream_agent_response
from chatkit.server import ChatKitServer
from chatkit.types import ThreadMetadata, ThreadStreamEvent, UserMessageItem
from memory_store import MemoryStore
from llmAgent import career_assistant

class MyAgentServer(ChatKitServer[dict[str, Any]]):
    """Server implementation that keeps conversation state in memory."""

    def __init__(self) -> None:
        self.store: MemoryStore = MemoryStore()
        super().__init__(self.store)

    async def respond(
        self,
        thread: ThreadMetadata,
        item: UserMessageItem | None,
        context: dict[str, Any],
    ) -> AsyncIterator[ThreadStreamEvent]:
        
        # 1. Generate a stable ID for this response ahead of time
        forced_id = f"msg_{uuid.uuid4().hex[:8]}"
        
        # 2. Pass this ID to the Store via context (so the DB uses it)
        context["forced_item_id"] = forced_id

        items_page = await self.store.load_thread_items(
            thread.id,
            after=None,
            limit=20,
            order="desc",
            context=context,
        )
        items = list(reversed(items_page.data))
        agent_input = await simple_to_agent_input(items)

        agent_context = AgentContext(
            thread=thread,
            store=self.store,
            request_context=context,
        )

        result = Runner.run_streamed(
            career_assistant,
            agent_input,
            context=agent_context,
        )

        async for event in stream_agent_response(agent_context, result):
            # 3. Patch the stream events to use the forced ID (so the UI uses it)
            if hasattr(event, "item_id") and (event.item_id == "__fake_id__" or not event.item_id):
                event.item_id = forced_id
            
            yield event