"""
app.py - Corona Review Intelligence - FastAPI Backend
Sprint 7: Vision upload, Tavily search, gpt-4o-mini vision, analyst mode removed,
          OpenAI Realtime voice tab added.
"""

# ── LangSmith env vars MUST be set before any LangChain imports ──────────────
import os
from dotenv import load_dotenv
load_dotenv(override=True)

os.environ["LANGCHAIN_TRACING_V2"]  = "true"
os.environ["LANGSMITH_TRACING"]     = "true"
os.environ["LANGCHAIN_API_KEY"]     = os.getenv("LANGCHAIN_API_KEY", "")
os.environ["LANGCHAIN_PROJECT"]     = os.getenv("LANGCHAIN_PROJECT", "corona-toilet-reviews")

# ── Now safe to import everything else ────────────────────────────────────────
import uuid
import re
import base64
import io
import json
import asyncio
from fastapi import FastAPI, UploadFile, File, Form, WebSocket, WebSocketDisconnect
from fastapi.responses import HTMLResponse
from fastapi.staticfiles import StaticFiles
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
import websockets as ws_lib

from chatbot import (
    build_chain, ask, get_followup_suggestions, log_feedback,
    get_vectorstore, clear_memory, get_last_trace_url,
    CORONA_KNOWLEDGE,
    web_search, get_weather, execute_code, query_products,
)

app = FastAPI(title="Corona Review Intelligence — Sprint 7")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

app.mount("/static", StaticFiles(directory="static"), name="static")

print("Loading agent chain...")
try:
    build_chain()
    print("Agent loaded successfully.")
    chain_loaded = True
except Exception as e:
    print(f"Error loading chain: {e}")
    chain_loaded = False

recent_runs = {}


# ── Request models ────────────────────────────────────────────────────────────
class ChatRequest(BaseModel):
    question: str
    session_id: str = ""

class FeedbackRequest(BaseModel):
    run_id: str
    score: int


# ── Routes ────────────────────────────────────────────────────────────────────
@app.get("/", response_class=HTMLResponse)
async def index():
    with open("static/index.html") as f:
        return HTMLResponse(content=f.read())


@app.post("/chat")
async def chat(request: ChatRequest):
    if not chain_loaded:
        return {"error": "Chatbot not initialized. Run ingest.py first."}

    question = request.question.strip()
    if not question:
        return {"error": "No question provided."}

    try:
        session_id = request.session_id or "default"
        answer, sources, show_stores = ask(question, role="customer", session_id=session_id)

        run_id = str(uuid.uuid4())
        recent_runs[run_id] = {"question": question, "answer": answer}

        suggestions = get_followup_suggestions(question, answer, "customer")
        trace_url = get_last_trace_url()

        return {
            "answer": answer,
            "run_id": run_id,
            "suggestions": suggestions,
            "show_stores": show_stores,
            "trace_url": trace_url,
        }
    except Exception as e:
        import traceback
        traceback.print_exc()
        return {"error": str(e)}


@app.post("/feedback")
async def feedback(request: FeedbackRequest):
    if request.run_id not in recent_runs:
        return {"error": "Run ID not found."}
    run_data = recent_runs[request.run_id]
    log_feedback(request.run_id, run_data["question"], run_data["answer"], request.score)
    return {"status": "ok"}


@app.post("/clear")
async def clear(request: ChatRequest = None):
    session_id = request.session_id if request else "default"
    clear_memory(session_id)
    return {"status": "cleared"}


@app.get("/health")
async def health():
    return {"status": "ok", "chain_loaded": chain_loaded}


# ── Sprint 7: Vision upload (multi-image) ────────────────────────────────────
@app.post("/upload-image")
async def upload_image(
    files: list[UploadFile] = File(...),
    caption: str = Form(default=""),
    session_id: str = Form(default="default"),
):
    """
    Accept one or more toilet photos, run vision analysis on each,
    return a combined response. Frontend sends multipart/form-data.
    """
    try:
        results = []

        for f in files:
            image_bytes = await f.read()
            b64 = base64.b64encode(image_bytes).decode("utf-8")
            question = caption.strip() or "Analyze this toilet image and recommend compatible seat covers."
            answer, sources, _ = ask(
                question=question,
                role="customer",
                session_id=session_id,
                image_b64=b64,
            )
            results.append({"filename": f.filename, "answer": answer, "sources": sources})

        # Combine answers if multiple images
        if len(results) == 1:
            combined = results[0]["answer"]
            sources = results[0]["sources"]
        else:
            parts = [f"📷 Image {i+1} ({r['filename']}):\n{r['answer']}" for i, r in enumerate(results)]
            combined = "\n\n---\n\n".join(parts)
            sources = list({s for r in results for s in r["sources"]})

        trace_url = get_last_trace_url()
        run_id = str(uuid.uuid4())
        recent_runs[run_id] = {"question": caption or "toilet image analysis", "answer": combined}
        return {
            "answer": combined,
            "run_id": run_id,
            "sources": sources,
            "show_stores": False,
            "vision": True,
            "image_count": len(results),
            "trace_url": trace_url,
        }
    except Exception as e:
        return {"error": str(e), "vision": True}


# ── Sprint 7: Whisper transcription (used by mic button) ─────────────────────
@app.post("/transcribe")
async def transcribe(file: UploadFile = File(...)):
    """Receive a recorded audio blob, transcribe via OpenAI Whisper, return text."""
    try:
        from openai import OpenAI
        client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))
        audio_bytes = await file.read()
        audio_file = io.BytesIO(audio_bytes)
        audio_file.name = file.filename or "recording.webm"
        transcript = client.audio.transcriptions.create(
            model="whisper-1",
            file=audio_file,
            language="es",
            prompt="Corona sanitarios Aquapro Montecarlo Smart Nyren Aluvia Cascade Cima Mansfield",
        )
        return {"transcript": transcript.text.strip()}
    except Exception as e:
        return {"error": str(e)}


# ── Sprint 7: OpenAI Realtime voice tab ──────────────────────────────────────

@app.get("/voice", response_class=HTMLResponse)
async def voice_page():
    with open("static/voice.html") as f:
        return HTMLResponse(content=f.read())


# Tool schemas for the Realtime session
_VOICE_TOOLS = [
    {
        "type": "function",
        "name": "web_search",
        "description": "Search the web for real-time info — news, sports scores, current events. Returns a direct answer plus sources.",
        "parameters": {
            "type": "object",
            "properties": {
                "query": {"type": "string", "description": "The search query"}
            },
            "required": ["query"]
        }
    },
    {
        "type": "function",
        "name": "get_weather",
        "description": "Get current weather for any city or location.",
        "parameters": {
            "type": "object",
            "properties": {
                "location": {"type": "string", "description": "City name or location"}
            },
            "required": ["location"]
        }
    },
    {
        "type": "function",
        "name": "query_products",
        "description": "Query the Corona toilet product database for specs, dimensions, ADA compliance, water consumption.",
        "parameters": {
            "type": "object",
            "properties": {
                "filter_description": {"type": "string", "description": "What to look up, e.g. 'ADA compliant toilets', 'dual flush models'"}
            },
            "required": ["filter_description"]
        }
    },
    {
        "type": "function",
        "name": "execute_code",
        "description": "Execute Python code for calculations, math, water savings estimates.",
        "parameters": {
            "type": "object",
            "properties": {
                "code": {"type": "string", "description": "Python code to run"}
            },
            "required": ["code"]
        }
    },
]


def _dispatch_voice_tool(name: str, args: dict) -> str:
    """Execute a voice tool call and return the result string."""
    try:
        if name == "web_search":
            return web_search.invoke(args.get("query", ""))
        elif name == "get_weather":
            return get_weather.invoke(args.get("location", ""))
        elif name == "query_products":
            return query_products.invoke(args.get("filter_description", ""))
        elif name == "execute_code":
            return execute_code.invoke(args.get("code", ""))
        else:
            return f"Unknown tool: {name}"
    except Exception as e:
        return f"Tool error: {e}"


_VOICE_INSTRUCTIONS = f"""You are Maya, a friendly voice assistant for Corona (Colombia) toilet products.
Keep responses CONCISE — 1-3 sentences max unless the user asks for more detail.
This is voice, not text — speak naturally, don't monologue, don't use bullet points or lists.

{CORONA_KNOWLEDGE}

Use the available tools when helpful:
- web_search: news, sports, current events
- get_weather: weather questions
- query_products: Corona toilet specs, dimensions, ADA compliance
- execute_code: calculations, math

Always respond in English. Be warm, friendly, and conversational."""


@app.websocket("/ws/voice")
async def voice_ws(websocket: WebSocket):
    """
    WebSocket bridge: browser ↔ OpenAI Realtime API.
    Browser sends raw PCM16 audio bytes.
    This endpoint forwards to OpenAI, handles tool calls, streams audio back.
    """
    await websocket.accept()

    oai_key = os.getenv("OPENAI_API_KEY", "")
    oai_uri = "wss://api.openai.com/v1/realtime?model=gpt-4o-mini-realtime-preview"
    oai_headers = [
        ("Authorization", f"Bearer {oai_key}"),
        ("OpenAI-Beta", "realtime=v1"),
    ]

    # macOS Python needs certifi SSL context to verify OpenAI's cert
    import ssl, certifi
    ssl_ctx = ssl.create_default_context(cafile=certifi.where())

    try:
        async with ws_lib.connect(oai_uri, additional_headers=oai_headers, ssl=ssl_ctx) as oai:
            # Configure the session
            await oai.send(json.dumps({
                "type": "session.update",
                "session": {
                    "modalities": ["audio", "text"],
                    "instructions": _VOICE_INSTRUCTIONS,
                    "voice": "coral",
                    "input_audio_format": "pcm16",
                    "output_audio_format": "pcm16",
                    "input_audio_transcription": {"model": "whisper-1"},
                    "turn_detection": {
                        "type": "server_vad",
                        "threshold": 0.82,         # high = ignores background noise, only clear speech
                        "prefix_padding_ms": 300,
                        "silence_duration_ms": 500, # short = natural convo, no awkward pauses
                    },
                    "tools": _VOICE_TOOLS,
                    "tool_choice": "auto",
                    "temperature": 0.7,
                }
            }))

            pending_calls: dict[str, dict] = {}

            async def browser_to_oai():
                """Forward browser audio frames to OpenAI."""
                while True:
                    try:
                        data = await websocket.receive_bytes()
                        await oai.send(json.dumps({
                            "type": "input_audio_buffer.append",
                            "audio": base64.b64encode(data).decode(),
                        }))
                    except WebSocketDisconnect:
                        break
                    except Exception:
                        break

            async def oai_to_browser():
                """Handle OpenAI events; tool calls resolved server-side."""
                async for raw in oai:
                    event = json.loads(raw)
                    etype = event.get("type", "")

                    if etype == "response.audio.delta":
                        # Forward raw PCM16 bytes to browser
                        audio_bytes = base64.b64decode(event["delta"])
                        try:
                            await websocket.send_bytes(audio_bytes)
                        except Exception:
                            break

                    elif etype in ("input_audio_buffer.speech_started", "response.cancelled"):
                        # Signal browser to flush in-flight audio (barge-in)
                        try:
                            await websocket.send_text(json.dumps({"type": "flush"}))
                        except Exception:
                            break

                    elif etype == "response.output_item.added":
                        item = event.get("item", {})
                        if item.get("type") == "function_call":
                            cid = item.get("call_id", "")
                            pending_calls[cid] = {"name": item.get("name", ""), "args": ""}

                    elif etype == "response.function_call_arguments.delta":
                        cid = event.get("call_id", "")
                        if cid in pending_calls:
                            pending_calls[cid]["args"] += event.get("delta", "")

                    elif etype == "response.function_call_arguments.done":
                        cid = event.get("call_id", "")
                        call = pending_calls.pop(cid, None)
                        if call:
                            try:
                                args = json.loads(event.get("arguments", "{}") or "{}")
                            except Exception:
                                args = {}
                            # Execute tool in thread pool (may block)
                            loop = asyncio.get_event_loop()
                            result = await loop.run_in_executor(
                                None, _dispatch_voice_tool, call["name"], args
                            )
                            await oai.send(json.dumps({
                                "type": "conversation.item.create",
                                "item": {
                                    "type": "function_call_output",
                                    "call_id": cid,
                                    "output": str(result)[:2000],  # cap length
                                }
                            }))
                            await oai.send(json.dumps({"type": "response.create"}))

                    elif etype in ("response.audio_transcript.delta", "conversation.item.input_audio_transcription.completed", "response.done", "session.created", "session.updated"):
                        # Forward state events as JSON text to browser for UI updates
                        try:
                            await websocket.send_text(raw)
                        except Exception:
                            break

                    elif etype == "error":
                        print(f"[Realtime] Error: {event.get('error', event)}")

            await asyncio.gather(browser_to_oai(), oai_to_browser())

    except WebSocketDisconnect:
        pass
    except Exception as e:
        print(f"[Voice WS] Error: {e}")
        try:
            await websocket.close()
        except Exception:
            pass


if __name__ == "__main__":
    import uvicorn
    uvicorn.run("app:app", host="127.0.0.1", port=8000, reload=True)
