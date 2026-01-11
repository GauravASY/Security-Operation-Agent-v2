"""
File-based store compatible with the ChatKit Store interface.
Persists chat history to a JSON file and ensures valid message IDs.
"""

from __future__ import annotations

import json
import os
import uuid
from collections import defaultdict

from chatkit.store import NotFoundError, Store
from chatkit.types import Attachment, Page, ThreadItem, ThreadMetadata
from pydantic import TypeAdapter

# Adapters for serialization
thread_adapter = TypeAdapter(ThreadMetadata)
item_adapter = TypeAdapter(ThreadItem)

DB_FILE = "chat_history.json"

class MemoryStore(Store[dict]):
    def __init__(self):
        self.threads: dict[str, ThreadMetadata] = {}
        self.items: dict[str, list[ThreadItem]] = defaultdict(list)
        self.attachments: dict[str, Attachment] = {}
        self._load_db()

    def _load_db(self):
        """Loads data from the JSON file."""
        if not os.path.exists(DB_FILE):
            return

        try:
            with open(DB_FILE, "r", encoding="utf-8") as f:
                data = json.load(f)

            for tid, t_data in data.get("threads", {}).items():
                self.threads[tid] = thread_adapter.validate_python(t_data)

            for tid, i_list in data.get("items", {}).items():
                self.items[tid] = [item_adapter.validate_python(i) for i in i_list]

            for att_id, att_data in data.get("attachments", {}).items():
                 # Assuming Attachment can be validated similarly or is a dict
                 if isinstance(att_data, dict):
                     # Reconstruct FileAttachment or ImageAttachment based on available fields or type
                     # For simplicity using direct dict or generic Attachment if possible
                     # TypeAdapter for Attachment (union) should work
                     pass
                 pass 
            
            # Better approach for attachments if type adapter is tricky without discriminator
            # But Attachment IS a Union in chatkit.types. Using TypeAdapter(Attachment)
            att_adapter = TypeAdapter(Attachment)
            for att_id, att_data in data.get("attachments", {}).items():
                self.attachments[att_id] = att_adapter.validate_python(att_data)
        except Exception as e:
            print(f"Warning: Could not load chat history: {e}")

    def _save_db(self):
        """Saves memory state to JSON file."""
        try:
            raw_data = {
                "threads": {
                    k: thread_adapter.dump_python(v, mode='json') 
                    for k, v in self.threads.items()
                },
                "items": {
                    k: [item_adapter.dump_python(i, mode='json') for i in v] 
                    for k, v in self.items.items()
                },
                "attachments": {
                    k:  TypeAdapter(Attachment).dump_python(v, mode='json')
                    for k, v in self.attachments.items()
                }
            }
            with open(DB_FILE, "w", encoding="utf-8") as f:
                json.dump(raw_data, f, indent=2, default=str)
        except Exception as e:
            print(f"Error saving chat history: {e}")

    def _ensure_valid_id(self, item: ThreadItem, context: dict = None):
        """
        Helper to fix invalid IDs.
        Checks context for a forced ID from the server, otherwise generates random.
        """
        if not item.id or item.id == "__fake_id__":
            if context and "forced_item_id" in context:
                item.id = context["forced_item_id"]
            else:
                item.id = f"msg_{uuid.uuid4().hex[:8]}"

    # --- Interface Implementation ---

    async def load_thread(self, thread_id: str, context: dict) -> ThreadMetadata:
        self._load_db()
        if thread_id not in self.threads:
            raise NotFoundError(f"Thread {thread_id} not found")
        return self.threads[thread_id]

    async def save_thread(self, thread: ThreadMetadata, context: dict) -> None:
        self.threads[thread.id] = thread
        self._save_db()

    async def load_threads(
        self, limit: int, after: str | None, order: str, context: dict
    ) -> Page[ThreadMetadata]:
        self._load_db()
        threads = list(self.threads.values())
        return self._paginate(
            threads,
            after,
            limit,
            order,
            sort_key=lambda t: t.created_at,
            cursor_key=lambda t: t.id,
        )

    async def load_thread_items(
        self, thread_id: str, after: str | None, limit: int, order: str, context: dict
    ) -> Page[ThreadItem]:
        self._load_db()
        items = self.items.get(thread_id, [])
        return self._paginate(
            items,
            after,
            limit,
            order,
            sort_key=lambda i: i.created_at,
            cursor_key=lambda i: i.id,
        )

    async def add_thread_item(
        self, thread_id: str, item: ThreadItem, context: dict
    ) -> None:
        # Pass context so we can grab the forced_id
        self._ensure_valid_id(item, context)
        
        self.items[thread_id].append(item)
        self._save_db()

    async def save_item(self, thread_id: str, item: ThreadItem, context: dict) -> None:
        # Pass context here too
        self._ensure_valid_id(item, context)

        if thread_id not in self.items:
            self.items[thread_id] = []
            
        items = self.items[thread_id]
        found = False
        
        for idx, existing in enumerate(items):
            if existing.id == item.id:
                items[idx] = item
                found = True
                break
        
        if not found:
            items.append(item)
            
        self._save_db()

    async def load_item(
        self, thread_id: str, item_id: str, context: dict
    ) -> ThreadItem:
        self._load_db()
        for item in self.items.get(thread_id, []):
            if item.id == item_id:
                return item
        raise NotFoundError(f"Item {item_id} not found in thread {thread_id}")

    async def delete_thread(self, thread_id: str, context: dict) -> None:
        self.threads.pop(thread_id, None)
        self.items.pop(thread_id, None)
        self._save_db()

    async def delete_thread_item(
        self, thread_id: str, item_id: str, context: dict
    ) -> None:
        self.items[thread_id] = [
            item for item in self.items.get(thread_id, []) if item.id != item_id
        ]
        self._save_db()

    def _paginate(
        self,
        rows: list,
        after: str | None,
        limit: int,
        order: str,
        sort_key,
        cursor_key,
    ):
        sorted_rows = sorted(rows, key=sort_key, reverse=order == "desc")
        start = 0
        if after:
            for idx, row in enumerate(sorted_rows):
                if cursor_key(row) == after:
                    start = idx + 1
                    break
        data = sorted_rows[start : start + limit]
        has_more = start + limit < len(sorted_rows)
        next_after = cursor_key(data[-1]) if has_more and data else None
        return Page(data=data, has_more=has_more, after=next_after)

    async def save_attachment(self, attachment: Attachment, context: dict) -> None:
        self.attachments[attachment.id] = attachment
        self._save_db()
    
    async def load_attachment(self, attachment_id: str, context: dict) -> Attachment:
        self._load_db()
        if attachment_id not in self.attachments:
            raise NotFoundError(f"Attachment {attachment_id} not found")
        return self.attachments[attachment_id]

    async def delete_attachment(self, attachment_id: str, context: dict) -> None:
        if attachment_id in self.attachments:
            del self.attachments[attachment_id]
            self._save_db()