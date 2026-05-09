# MAYA — Code Map
### How the system actually works · file by file · for "explain your code"

---

## 1. SYSTEM FLOW (one diagram)

```
   USER (browser: chat or voice)
        │
        ▼
   ┌─────────────────────────────────────────┐
   │  app.py  (FastAPI server, port 8000)    │
   │  Endpoints: /chat /voice /ws/voice      │
   │            /upload-image /transcribe    │
   └────────────────────┬────────────────────┘
                        │
                        ▼
   ┌─────────────────────────────────────────┐
   │  chatbot.py → ask(question, image_b64)  │
   │  THE BRAIN                              │
   └────────────────────┬────────────────────┘
                        │
        ┌───────────────┴───────────────┐
        ▼                               ▼
   detect_injection()              get_clock_string()
   (8 attack patterns)         (inject current date/time)
        │                               │
        └───────────────┬───────────────┘
                        ▼
   ┌─────────────────────────────────────────┐
   │  ROUTING — first match wins             │
   ├─────────────────────────────────────────┤
   │  1. META keywords    → architecture LLM │
   │  2. image_b64        → VISION pipeline  │
   │  3. SEARCH keywords  → Tavily + polish  │
   │  4. COMPANY keywords → CORONA_KNOWLEDGE │
   │  5. CODE keywords    → execute_code     │
   │  6. TABLE keywords   → product_table    │
   │  7. fallback         → ReAct agent      │
   └────────────────────┬────────────────────┘
                        ▼
   ┌─────────────────────────────────────────┐
   │  ChromaDB RAG (k=8)                     │
   │  + PRODUCT_SOURCE_MAP filter            │
   │  → context fed into agent               │
   └────────────────────┬────────────────────┘
                        ▼
   ┌─────────────────────────────────────────┐
   │  LangGraph ReAct Agent (gpt-4o-mini)    │
   │  Thought → Action → Observation loop    │
   │  Picks any of 6 tools as needed         │
   └────────────────────┬────────────────────┘
                        ▼
              strip_markdown()
                        ▼
              LangSmith trace URL
                        ▼
              JSON response → frontend
```

---

## 2. FILES — what each one does

| File | Purpose | Key functions |
|------|---------|---------------|
| `app.py` | FastAPI server, all HTTP/WebSocket endpoints | `chat()`, `voice_ws()`, `upload_image()` |
| `chatbot.py` | The brain — agent, all 6 tools, routing, RAG | `ask()`, `build_chain()`, all `@tool` defs |
| `sprint7/clock/inject.py` | Injects current date+time into every prompt | `get_clock_string()` |
| `sprint7/vision/tool.py` | LangChain `@tool` wrapping the vision pipeline | `build_vision_tool()` |
| `sprint7/vision/yolo_client.py` | HTTP client → YOLO at `localhost:8001` | `classify_toilet()` |
| `sprint7/vision/nim_fallback.py` | GPT-4o-mini vision fallback + photo coaching | `vision_fallback()` |
| `static/index.html` | Chat UI — messages, image upload, mic button | (frontend only) |
| `static/voice.html` | Voice UI — animated orb, WebSocket bridge | (frontend only) |
| `chroma_db/` | Vector store — 1,100+ chunks, persistent | (data, not code) |
| `.env` | API keys: OpenAI, Tavily, LangSmith | (config) |

---

## 3. THE 6 TOOLS — what each one does

| Tool | Purpose | Inside (key calls) |
|------|---------|-------------------|
| `get_weather(city)` | Live weather for any city | HTTP GET `wttr.in/{city}?format=3` |
| `web_search(query)` | Real-time web — news, sports, current events | `TavilyClient.search(include_answer=True)` |
| `query_products(filter)` | Corona product specs from review database | `_vectorstore.similarity_search(k=10)` |
| `generate_product_table(attrs)` | HTML comparison table of products | regex extracts specs, builds `<table>` |
| `execute_code(code)` | Sandboxed Python (math, stats, dates) | `exec()` with restricted builtins, 8 blocked patterns |
| `analyze_toilet_image(image_b64)` | Identify toilet model + recommend seat covers | YOLO `:8001` → GPT-4o-mini fallback |

---

## 4. ROUTING — why bypasses exist

The ReAct agent CAN pick any tool, but it adds 1-2s of reasoning per turn. For high-confidence patterns we **skip the agent** and call the tool directly. Same accuracy, faster response.

| Bypass | Trigger keywords | Action |
|--------|------------------|--------|
| **META** | "how do you work", "what model", "your code", "architecture" | Direct LLM call with architecture knowledge |
| **VISION** | `image_b64` parameter present | Two-stage: YOLO → vision LLM fallback |
| **SEARCH** | "search", "who won", "latest news", "score" | Tavily + context injection + today's date |
| **COMPANY** | "corona founded", "ceo", "mansfield", "echavarria" | Direct LLM with `CORONA_KNOWLEDGE` block |
| **CODE** | "run python", "calculate", "write a script" | LLM generates Python → `execute_code` |
| **TABLE** | "comparison table", "table of products" | `generate_product_table` directly |
| **fallback** | none of the above | RAG → ReAct agent picks tool itself |

---

## 5. HOW RAG WORKS

```
User question
     ↓
ChromaDB.similarity_search(k=8)   ← base retrieval
     ↓
Does question mention a product? (Nyren, Aluvia, Cascade, Smart, Cima)
     ↓ YES
PRODUCT_SOURCE_MAP filter → search WITHIN that product's source file (k=20)
     ↓ NO
Topic-aware expansion: install / specs / maintenance keywords add a 2nd query
     ↓
Combined chunks → context (top 20) → fed into the agent prompt
```

This was the Sprint 6 fix. Random `.get()` ordering was returning cover pages instead of relevant chunks. Now we filter by source.

---

## 6. SECURITY LAYERS

1. **`detect_injection()`** runs before the LLM is even called. 8 regex patterns: "ignore previous," "act as," "reveal your prompt," etc. Match → polite refusal.
2. **System prompt has `ROLE_LOCK`** appended — explicit instructions never to change persona or reveal internals.
3. **`execute_code` sandbox** — strips imports, blocks `open`, `subprocess`, `eval`, `socket`, `urllib`. Restricted builtins only.

---

## 7. OBSERVABILITY

Every `ask()` is wrapped in `@traceable` from LangSmith. After every response, we expose `_last_trace_url` — the user can click through to inspect retrieved chunks, every tool call, latencies, and token counts.

---

## 8. STACK SUMMARY

| Layer | Technology |
|-------|-----------|
| API server | FastAPI |
| LLM | GPT-4o-mini (chat) + gpt-4o-mini-realtime-preview (voice) + gpt-4o-mini vision (CV fallback) |
| Agent framework | LangGraph `create_react_agent` |
| Vector store | ChromaDB (local, persistent) |
| Embeddings | OpenAI text-embedding-3-small (1536-dim) |
| Web search | Tavily (`include_answer=True`, `search_depth=advanced`) |
| Weather | wttr.in (no key needed) |
| Voice | OpenAI Realtime API over WebSocket |
| Computer Vision | YOLOv8 (port 8001) + GPT-4o-mini vision fallback |
| Tracing | LangSmith |
| Memory | `InMemoryChatMessageHistory` per session_id |
