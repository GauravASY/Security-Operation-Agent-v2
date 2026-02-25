from typing import List, Dict, Optional, AsyncIterator, Any
import uuid
import json
import re
import traceback
from datetime import datetime

from agents import Runner
from chatkit.agents import AgentContext, simple_to_agent_input, stream_agent_response
from chatkit.server import ChatKitServer
from chatkit.types import ThreadMetadata, ThreadStreamEvent, UserMessageItem, AssistantMessageItem, ThreadItemAddedEvent, ThreadItemDoneEvent, InferenceOptions
from memory_store import MemoryStore
from attachmentStore import BlobAttachmentStore
from llmAgent import career_assistant
from utils import handling_wazuh_agent

# Import your tools so they can be executed inside the server
from tools import (
    get_file_content_raw, 
    search_indicators_by_report_raw, 
    search_by_victim_raw, 
    get_reportsID_by_technique_raw, 
    get_reports_by_reportID_raw
)

class MyAgentServer(ChatKitServer[dict[str, Any]]):
    """Server implementation that keeps conversation state in memory."""

    def __init__(self) -> None:
        self.store: MemoryStore = MemoryStore()
        self.attachment_store: BlobAttachmentStore = BlobAttachmentStore(store=self.store)
        super().__init__(store=self.store, attachment_store=self.attachment_store)

    async def respond(
        self,
        thread: ThreadMetadata,
        item: UserMessageItem | None,
        context: dict[str, Any],
    ) -> AsyncIterator[ThreadStreamEvent]:
        
        # 1. Generate a stable ID for this response ahead of time
        forced_id = f"msg_{uuid.uuid4().hex[:8]}"
        context["forced_item_id"] = forced_id

        # 2. Load History from Store
        items_page = await self.store.load_thread_items(
            thread.id,
            after=None,
            limit=20,
            order="desc",
            context=context,
        )
        # Convert ChatKit items to a list of dicts for the manual loop
        # Note: We reverse it to get chronological order
        db_items = list(reversed(items_page.data))
        conversation_chain = []
        
        for db_item in db_items:
            role = "user" if isinstance(db_item, UserMessageItem) else "assistant"
            # create conversation chain for text and attachments( consider user/assistant/user/assistant constraint)
            if db_item.content and len(db_item.content) > 0:
                 if hasattr(db_item.content[0], 'text'):
                    conversation_chain.append({"role": role, "content": db_item.content[0].text})

        # Add the current new item if it exists and isn't in DB yet
        # Check if the last message in chain is the same as item to avoid duplication.
        if item and len(item.content) == 0 and len(item.attachments) > 0:
            synthetic_user_item = UserMessageItem(
            id=f"msg_{uuid.uuid4().hex[:8]}",
            thread_id=thread.id,
            created_at=datetime.utcnow(),
            content=[{"type": "input_text", "text": f"User uploaded a file {item.attachments[0].name}"}],
            inference_options=InferenceOptions(tool_choice=None, model=None)
        )

            yield ThreadItemAddedEvent(item=synthetic_user_item)
            yield ThreadItemDoneEvent(item=synthetic_user_item)
            assistant_item = AssistantMessageItem(
                id=forced_id,
                thread_id=thread.id,
                created_at=datetime.utcnow(),
                content=[{"type": "output_text", "text": "File upload successful."}],
            )

            yield ThreadItemAddedEvent(item=assistant_item)
            yield ThreadItemDoneEvent(item=assistant_item)

            return
                  
        # adding the user message to the conversation chain if already not present
        if item and item.content and hasattr(item.content[0], 'text'):
            current_text = item.content[0].text
            if item.attachments and len(item.attachments) > 0 and hasattr(item.attachments[0], 'name'):
                final_text = f"User uploaded a file {item.attachments[0].name} and asked {current_text}" 
                if not conversation_chain or conversation_chain[-1]['content'] != current_text:
                    conversation_chain.append({"role": "user", "content": final_text})
                else:
                    #remove last item from conversation chain
                    conversation_chain.pop()
                    conversation_chain.append({"role": "user", "content": final_text})
            else:
                if not conversation_chain or conversation_chain[-1]['content'] != current_text:
                    conversation_chain.append({"role": "user", "content": current_text})
                

        # 3. Start the ReAct Loop (Max Turns)
        max_turns = 5
        
        for turn in range(max_turns):
            full_turn_response = ""
            tool_calls_found = False
            buffered_events = []  # Buffer events instead of yielding immediately

            # Prepare Context
            agent_context = AgentContext(
                thread=thread,
                store=self.store,
                attachment_store=self.attachment_store,
                request_context=context,
            )

            # Note: We pass the conversation_chain list directly as input
            result = Runner.run_streamed(
                career_assistant,
                conversation_chain, 
                context=agent_context,
            )

            # Stream response to client AND capture text for regex
            async for event in stream_agent_response(agent_context, result):
                # Patch the stream events to use the forced ID
                if hasattr(event, "item_id") and (event.item_id == "__fake_id__" or not event.item_id):
                    event.item_id = forced_id
                
                # Capture text from thread.item.done events
                if event.type == "thread.item.done" and hasattr(event, "item"):
                    item_obj = event.item
                    if hasattr(item_obj, "content") and item_obj.content:
                        for part in item_obj.content:
                            if hasattr(part, "text"):
                                full_turn_response += part.text

                buffered_events.append(event)

            try:
                match = re.search(r'(\[\s*\{\s*"name"\s*:\s*"(?:get_file_content|get_file_content_raw|search_indicators_by_report|search_indicators_by_report_raw|search_by_victim|search_by_victim_raw|get_reportsID_by_technique|get_reportsID_by_technique_raw|get_reports_by_reportID|get_reports_by_reportID_raw|wazuh_agent|analyse_wazuh_data|analyse_wazuh_data_raw)".*?\])', full_turn_response, re.DOTALL)
                
                if match:
                    possible_json = match.group(1)
                    print(f"Main Agent from line 150: {possible_json}")
                    tool_calls = json.loads(possible_json)
                    if isinstance(tool_calls, list):
                        tool_calls_found = True
                        
                        tool_outputs = []
                        for call in tool_calls:
                            # --- Execute Tools ---
                            res = "Error: Unknown tool"
                            name = call.get("name", "")
                            # Normalize: strip _raw suffix so both variants work
                            if name.endswith("_raw"):
                                name = name[:-4]
                            args = call.get("arguments", {})
                            
                            try:
                                if name == "search_indicators_by_report":
                                    res = await search_indicators_by_report_raw(**args)
                                elif name == "get_file_content":
                                    res = await get_file_content_raw(**args)
                                elif name == "search_by_victim":
                                    res = await search_by_victim_raw(**args)
                                elif name == "get_reportsID_by_technique":
                                    res = await get_reportsID_by_technique_raw(**args)
                                elif name == "get_reports_by_reportID":
                                    res = await get_reports_by_reportID_raw(**args)
                                elif name == "wazuh_agent":
                                    # Stream Wazuh response directly to UI in real-time
                                    # Always use the model's explicit input arg, never fall back to
                                    # item.content which may contain prior conversation context
                                    wazuh_query = "Start Wazuh Analysis"
                                    try:
                                        wazuh_response_item = None  # Capture the item for saving
                                        
                                        # Iterate over the async generator and yield events to UI
                                        async for event in handling_wazuh_agent(wazuh_query, agent_context):
                                            yield event
                                            # Capture the done item for explicit saving
                                            if event.type == "thread.item.done" and hasattr(event, "item"):
                                                wazuh_response_item = event.item
                                        
                                        # Explicitly save to ensure conversation history is preserved
                                        if wazuh_response_item:
                                            await self.store.save_item(thread.id, wazuh_response_item, context)
                                            print("Wazuh response saved to memory store")
                                        
                                        # Exit immediately after Wazuh completes - no second Main Agent call
                                        print("Wazuh streaming complete, exiting respond method")
                                        return
                                        
                                    except Exception as e:
                                        print(f"Error running wazuh_agent: {e}")
                                        traceback.print_exc()
                                        res = f"Error during Wazuh Analysis: {e}"
                            except Exception as tool_err:
                                print(f"CRITICAL ERROR executing tool {name}: {tool_err}")
                                traceback.print_exc()
                                res = f"Tool Execution Error: {tool_err}"
                            
                            tool_outputs.append(res)
                        
                        # Update Chain for next iteration
                        conversation_chain.append({"role": "assistant", "content": full_turn_response})
                        conversation_chain.append({"role": "user", "content": f"Tool Output: {json.dumps(tool_outputs)}"})
                        
                        # Generate a NEW ID for the next chunk of text (the answer after tools)
                        forced_id = f"msg_{uuid.uuid4().hex[:8]}"
                        context["forced_item_id"] = forced_id
                        
            except json.JSONDecodeError as e:
                print(f"JSON Decode Error for tool call: {e}")
                print(f"Failed JSON string: {possible_json}")
            except Exception as e:
                print(f"Error parsing tool call: {e}")
                traceback.print_exc()

            if not tool_calls_found:
                for event in buffered_events:
                    yield event
                break