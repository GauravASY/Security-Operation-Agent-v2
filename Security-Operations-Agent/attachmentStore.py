from chatkit.store import AttachmentStore
from chatkit.types import AttachmentCreateParams, Attachment, FileAttachment, AttachmentUploadDescriptor
from uuid import uuid4
from typing import Any
from memory_store import MemoryStore


BASE_URL = "http://localhost:8000"

class BlobAttachmentStore(AttachmentStore[dict]):
    def __init__(self, store: MemoryStore = None):
        self.store = store or MemoryStore()

    def generate_attachment_id(self, mime_type: str, context: dict) -> str:
        return f"att_{uuid4().hex}"

    async def create_attachment(
        self, input: AttachmentCreateParams, context: dict
    ) -> Attachment:
        
        att_id = self.generate_attachment_id(input.mime_type, context)
        upload_url = f"{BASE_URL}/api/upload?filename={input.name}" 
        upload_descriptor = AttachmentUploadDescriptor(url=upload_url, method="PUT")
        attachment = FileAttachment(
            id=att_id,
            mime_type=input.mime_type,
            name=input.name,
            upload_descriptor=upload_descriptor,
            type="file",
        )
        await self.store.save_attachment(attachment, context=context)
        return attachment

    async def load_attachment(self, attachment_id: str, context: dict) -> Attachment:
        return await self.store.load_attachment(attachment_id, context)

    async def delete_attachment(self, attachment_id: str, context: dict) -> None:
        await self.store.delete_attachment(attachment_id, context)