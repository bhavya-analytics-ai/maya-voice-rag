# MAYA Voice Tab — Implementation Details
### Sprint 7 · What we built, how it works, why each decision was made

---

## What it is

A real-time voice agent. User speaks → Maya listens → Maya responds in audio. No button to stop/start — server-side Voice Activity Detection (VAD) handles it automatically. Same brain as the chat tab, different surface.

URL: `localhost:8000/voice` (also accessible via ngrok public URL)

---

## Files involved

| File | Role |
|------|------|
| `static/voice.html` | Frontend — animated orb UI, WebSocket client, audio capture + playback |
| `app.py` `/voice` route | Serves `voice.html` |
| `app.py` `/ws/voice` | **The bridge** — WebSocket handler that connects browser to OpenAI Realtime API |
| `app.py` `_VOICE_TOOLS` | Tool schemas exposed to the Realtime session |
| `app.py` `_VOICE_INSTRUCTIONS` | Voice system prompt (with full CORONA_KNOWLEDGE injected) |
| `app.py` `_dispatch_voice_tool()` | Executes tool calls the Realtime model makes |
| `chatbot.py` | Source of the 4 tools wired into voice (web_search, get_weather, query_products, execute_code) |

---

## Audio flow — step by step

```
Browser mic (getUserMedia)
    ↓
MediaRecorder / AudioWorklet captures raw PCM16 audio chunks
    ↓
WebSocket → FastAPI /ws/voice
    ↓
app.py: browser_to_oai() coroutine
    ↓ base64-encodes and sends:
    { "type": "input_audio_buffer.append", "audio": "<b64>" }
    ↓
OpenAI Realtime API (wss://api.openai.com/v1/realtime)
    ↓ VAD detects end of speech
    ↓ gpt-4o-mini-realtime-preview generates response
    ↓ streams back: response.audio.delta events (base64 PCM16 chunks)
    ↓
app.py: oai_to_browser() coroutine decodes and sends raw bytes
    ↓
Browser: AudioContext plays PCM16 chunks in real time
```

---

## Voice Activity Detection (VAD)

We use **server-side VAD** — OpenAI's model detects when the user stops talking, not the browser.

```python
"turn_detection": {
    "type": "server_vad",
    "threshold": 0.82,          # speech confidence to start recording
    "prefix_padding_ms": 300,   # ms of audio before speech to include
    "silence_duration_ms": 500, # ms of silence = end of turn
}
```

**Why 0.82 threshold:** Lower picks up keyboard taps, background noise, paper rustling. 0.82 = only responds to clear speech.

**Why 500ms silence:** Natural conversational pause. Lower = cuts off slow speakers. Higher = awkward dead air before Maya responds.

---

## Tool calls in voice

The Realtime model can call tools mid-conversation. Here's how:

```
User speaks → Realtime model decides to call a tool
    ↓
response.output_item.added  → pending_calls[call_id] = {name, args}
response.function_call_arguments.delta → streams args JSON
response.function_call_arguments.done → args complete
    ↓
app.py runs _dispatch_voice_tool(name, args) in thread pool
    (thread pool = doesn't block the async event loop)
    ↓
Result sent back:
    { "type": "conversation.item.create", "item": { "type": "function_call_output", ... } }
    { "type": "response.create" }  ← triggers Maya to speak the result
```

**4 tools wired in voice:**
- `web_search` — Tavily search
- `get_weather` — wttr.in
- `query_products` — ChromaDB similarity search
- `execute_code` — sandboxed Python

Note: `analyze_toilet_image` is NOT in voice — requires image upload, not audio.

---

## Session configuration

```python
"session": {
    "modalities": ["audio", "text"],         # both audio in/out AND text transcript
    "voice": "coral",                         # tested all voices, coral = clearest
    "input_audio_format": "pcm16",           # raw PCM, 24kHz, 16-bit
    "output_audio_format": "pcm16",
    "input_audio_transcription": {"model": "whisper-1"},  # get text transcript too
    "temperature": 0.7,
    "tool_choice": "auto",                    # model decides when to use tools
}
```

---

## Barge-in (user interrupting Maya)

When Maya is mid-response and the user starts speaking:

```
OpenAI sends: input_audio_buffer.speech_started or response.cancelled
    ↓
app.py sends: { "type": "flush" } to browser
    ↓
Frontend stops playing buffered audio immediately
```

This makes it feel like a real conversation — you can cut Maya off.

---

## SSL fix (macOS specific)

macOS Python doesn't use the system cert store. Connecting to OpenAI's WebSocket would fail with SSL errors without this:

```python
import ssl, certifi
ssl_ctx = ssl.create_default_context(cafile=certifi.where())
async with ws_lib.connect(oai_uri, additional_headers=oai_headers, ssl=ssl_ctx) as oai:
```

`certifi` provides Mozilla's trusted CA bundle. Installed in requirements.txt.

---

## Browser AEC (echo cancellation)

```javascript
navigator.mediaDevices.getUserMedia({
    audio: {
        echoCancellation: true,   // prevents Maya's voice from being picked up by mic
        noiseSuppression: true,
        sampleRate: 24000,
    }
})
```

Without AEC, Maya hears herself → infinite loop of responses.

---

## Animated orb states

| State | When | Visual |
|-------|------|--------|
| `idle` | Waiting for user to speak | Slow pulse, dim |
| `listening` | User is speaking (VAD active) | Bright pulse, faster |
| `thinking` | Realtime model processing | Spinning/rotating |
| `speaking` | Maya's audio playing back | Ripple outward |

State transitions driven by WebSocket events from OpenAI:
- `input_audio_buffer.speech_started` → listening
- `response.created` → thinking
- `response.audio.delta` → speaking
- `response.done` → idle

---

## Key Q&A for the demo

**Q: "How does the voice connection work?"**
Browser WebSocket → FastAPI /ws/voice → bridges to OpenAI Realtime API. Audio streams both ways as 24kHz PCM16. Server VAD detects end of speech, model generates, audio streams back.

**Q: "Why server-side VAD instead of client-side?"**
Client VAD = we'd ship audio to the server only after we think user stopped. Server VAD = continuous audio stream, OpenAI decides in real-time. More accurate, less latency.

**Q: "How do tools work in voice?"**
OpenAI Realtime model decides to call a tool → sends function_call event → app.py executes the actual Python function → result returned to model → model speaks the answer.

**Q: "What if the WebSocket drops?"**
Frontend detects close event and shows reconnect prompt. Session memory (last 10 turns) is in-process RAM — reconnecting creates a fresh session. Conversation history doesn't persist across disconnections.

**Q: "Why coral voice?"**
Tested all available voices. Coral = clearest articulation, neutral accent, works for both English and Spanish product names.

**Q: "Why NOT include vision in voice?"**
Voice is real-time audio only. Image upload is a separate interaction (multipart form). Mixing them would require the user to somehow "send" an image mid-conversation — bad UX. Different tools for different surfaces.

**Q: "What's the latency?"**
First audio chunk arrives 600-900ms after user stops speaking. End-to-end with tool calls: 1.5-3s depending on tool (Tavily search ≈ +500ms).

---

## Start commands

```bash
# Everything (MAYA + YOLO + ngrok):
bash ~/Desktop/start_maya.sh

# Just MAYA:
cd /Users/ompandya/Desktop/chatbot-corona
python3 -m uvicorn app:app --host 0.0.0.0 --port 8000

# Voice tab:
open http://localhost:8000/voice
```

If voice disconnects immediately → check `/tmp/maya.log` for SSL errors → certifi fix already in code.
