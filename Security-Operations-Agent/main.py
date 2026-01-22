from agents import Runner, trace, set_tracing_export_api_key
from openai.types.responses import ResponseTextDeltaEvent
import  os
from dotenv import load_dotenv
load_dotenv()
from tools import get_file_content, search_indicators_by_report, search_by_victim, get_reportsID_by_technique, get_reports_by_reportID
from vectorstore import ingest_txt
from utils import upload_file_to_s3
from database import init_db
import uvicorn

from chatkit.server import StreamingResult
from fastapi import FastAPI, Request, UploadFile, File
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse, Response, StreamingResponse
from chatkit_server import MyAgentServer
import shutil

app = FastAPI(title="ChatKit Backend")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

chatkit_server = MyAgentServer()


@app.post("/chatkit")
async def chatkit_endpoint(request: Request) -> Response:
    """Proxy the ChatKit web component payload to the server implementation."""
    payload = await request.body()
    result = await chatkit_server.process(payload, {"request": request})

    if isinstance(result, StreamingResult):
        return StreamingResponse(result, media_type="text/event-stream")
    if hasattr(result, "json"):
        return Response(content=result.json, media_type="application/json")
    return JSONResponse(result)


UPLOAD_DIR = "temp_uploads"
os.makedirs(UPLOAD_DIR, exist_ok=True)

@app.put("/api/upload")
async def handle_file_upload(request: Request, filename: str):
    file_path = os.path.join(UPLOAD_DIR, filename)
    
    # Save file
    content = await request.body()
    with open(file_path, "wb") as buffer:
        buffer.write(content)

    s3_response = upload_file_to_s3(file_path, os.environ.get("S3_BUCKET_NAME"))   
    result = await ingest_txt(file_path, s3_url=s3_response)
    print("Result for file upload : ", result)


if __name__ == "__main__":
    init_db()
    uvicorn.run(app, host="0.0.0.0", port=8000)
