# MAYA — Sprint 7 README

## What is MAYA
AI chatbot for Corona (Colombia) toilet products. Answers customer questions using 1,100+ chunks of real product docs (PDFs, Word files) and reviews, with live web search, computer vision for seat cover matching, and a realtime voice interface.

---

## Start / Stop

```bash
# Start everything (MAYA + YOLO + ngrok)
bash ~/Desktop/start_maya.sh

# Stop everything
pkill -f "uvicorn|ngrok"

# Restart
pkill -f "uvicorn|ngrok" && sleep 2 && bash ~/Desktop/start_maya.sh

# Check what's running
ps aux | grep -E "uvicorn|ngrok" | grep -v grep

# Logs
tail -f /tmp/maya.log   # MAYA
tail -f /tmp/yolo.log   # YOLO
tail -f /tmp/ngrok.log  # ngrok
```

---

## Services

| Service | Port | What it does |
|---------|------|-------------|
| MAYA (FastAPI) | 8000 | Main chatbot — chat, image upload, voice |
| YOLO (FastAPI) | 8001 | Toilet brand detection (Aquapro / Montecarlo / Smart) |
| ngrok | — | Public URL tunnel → port 8000, share with friends |

**Health check:**
```bash
curl http://localhost:8000/health   # → {"status":"ok","chain_loaded":true}
curl http://localhost:8001/         # → {"status":"API running"}
```

---

## URLs

| Page | URL |
|------|-----|
| Chat | `http://localhost:8000/` |
| Voice | `http://localhost:8000/voice` |
| Public (ngrok) | Printed by start_maya.sh — changes every restart |

---

## Key files

```
MAYA/
├── app.py                        # FastAPI server — all routes
├── chatbot.py                    # Brain — agent, tools, RAG, all bypasses
├── ingest.py                     # Re-ingests docs into ChromaDB
├── mcp_server.py                 # MCP server — 6 tools exposed
├── scrape_corona.py              # Data scraping
├── requirements.txt
├── README.md
├── static/
│   ├── index.html                # Chat UI
│   └── voice.html                # Voice orb UI
├── context/                      # Source docs (PDFs, Word, CSVs)
├── modules/
│   ├── vision/
│   │   ├── tool.py               # @tool analyze_toilet_image
│   │   ├── yolo_client.py        # Calls YOLO at :8001
│   │   └── nim_fallback.py       # gpt-4o-mini vision fallback
│   ├── clock/
│   │   └── inject.py             # Injects current date/time into prompts
│   ├── pipeline/                 # Orchestrator
│   └── tests/                   # Demo questions
├── docs/                         # RUNNING.md, VOICE_README.md, TESTING.md, CODE_MAP.md
├── reports/                      # Individual reports
├── presentations/                # HTML decks
└── notebooks/                    # Jupyter notebooks
```

---

## .env keys

```env
OPENAI_API_KEY=sk-proj-...              # GPT-4o-mini, Whisper, vision, Realtime API
LANGCHAIN_API_KEY=lsv2_pt_...          # LangSmith tracing
LANGCHAIN_TRACING_V2=true
LANGCHAIN_PROJECT=corona-toilet-reviews
TAVILY_API_KEY=tvly-dev-...            # Web search (Tavily)
```

---

## How questions get answered

```
User question
  │
  ├─ Injection check (blocks jailbreaks)
  │
  ├─ META_TRIGGERS (architecture / company questions)
  │     → answered directly from CORONA_KNOWLEDGE hardcoded block
  │
  ├─ Image uploaded?
  │     → YOLO (Aquapro/Montecarlo/Smart detection)
  │     → falls back to gpt-4o-mini vision if YOLO confidence < 0.4
  │     → returns matching seat covers + photo coaching if image unclear
  │
  ├─ SEARCH_KEYWORDS ("who won", "latest news", "search for"...)
  │     → Tavily advanced search + include_answer (direct answer)
  │     → short queries get previous message + today's date injected for context
  │
  ├─ COMPANY_KEYWORDS ("who founded corona", "mansfield", "ceo"...)
  │     → answered directly from CORONA_KNOWLEDGE block
  │
  ├─ CODE_KEYWORDS ("calculate", "write python", "run code"...)
  │     → GPT-4o-mini generates Python → sandboxed execute_code tool runs it
  │
  ├─ TABLE_KEYWORDS ("comparison table", "show a table"...)
  │     → generate_product_table tool → returns HTML table
  │
  └─ Everything else
        → ChromaDB similarity search (k=8 + PRODUCT_SOURCE_MAP boost)
        → LangGraph ReAct agent with GPT-4o-mini
        → Tools available: get_weather, web_search, query_products, generate_product_table, execute_code, analyze_toilet_image
```

---

## Sprint 7 changes (vs Sprint 6)

### 1. Tavily search (replaced DuckDuckGo)
`web_search` tool uses Tavily with `search_depth="advanced"` and `include_answer=True`. Tavily generates a direct answer from the web — much faster and more accurate. Key in `.env`.

### 2. Context injection for ambiguous queries
Short queries like "who won?" now pull the previous user message from memory + today's date before hitting Tavily. Fixes the "who won what?" problem.

### 3. gpt-4o-mini vision (replaced NVIDIA NIM)
`modules/vision/nim_fallback.py` uses gpt-4o-mini vision instead of NVIDIA NIM. Same OpenAI key, no extra account needed. Also gives photo coaching tips when the image is too blurry/dark.

### 4. Analyst mode removed
No lock button, no radar panel, no analyst password. Everything is customer mode. Cleaner codebase.

### 5. OpenAI Realtime voice tab
- `/voice` — animated orb UI, coral voice
- `/ws/voice` — FastAPI WebSocket bridge to OpenAI Realtime API
- Server VAD: threshold=0.82 (ignores background noise), silence=500ms (natural feel)
- Browser echo cancellation via `echoCancellation:true` in getUserMedia
- Tools available in voice: web_search, get_weather, query_products, execute_code
- Full CORONA_KNOWLEDGE in voice system prompt

---

## Voice tab — how it works

```
Browser mic (getUserMedia, echoCancellation:true)
  → 48kHz Float32 → downsample to 24kHz Int16 PCM
  → WebSocket → /ws/voice (FastAPI)
  → forwarded to OpenAI Realtime API (wss://api.openai.com/v1/realtime)

OpenAI Realtime
  → server VAD detects speech
  → streams audio response (coral voice, 24kHz PCM)
  → tool calls handled server-side (web_search, etc.)
  → audio chunks → /ws/voice → browser
  → browser plays via AudioContext (gapless scheduling)
  → barge-in: speech_started event → flush queued audio → Maya stops talking
```

Click the orb or the mic button to start. Browser asks for mic permission once.

---

## If something breaks

| Problem | Fix |
|---------|-----|
| Voice disconnects immediately | `tail -f /tmp/maya.log` — probably SSL error. Run `/Applications/Python\ 3.13/Install\ Certificates.command` |
| YOLO not running | `cd ~/Desktop/cv-sprint-yolo && nohup python3 -m uvicorn api_yolo:app --host 0.0.0.0 --port 8001 > /tmp/yolo.log 2>&1 &` |
| Web search returning placeholder error | Tavily key not in .env or expired |
| Voice gets interrupted by background noise | Increase VAD threshold in app.py `/ws/voice` session config (currently 0.82, push to 0.88) |
| Server not picking up code changes | Kill and restart — no `--reload` flag used |
| ngrok URL changed | Re-run `start_maya.sh`, new URL is printed |
