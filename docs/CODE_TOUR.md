# MAYA Code Defense — Sprint 7

Quick answers for every question the professor might ask during live demo.

---

## "How does the agent reason?"

MAYA uses LangGraph's `create_react_agent` — a ReAct loop (Reason + Act).

Every question goes through:
1. **Tool selection** — agent decides which tool to call (or none)
2. **Tool execution** — result fed back to agent
3. **Final answer** — agent synthesizes and responds

You can watch every step live in **LangSmith** → `corona-toilet-reviews` project.

---

## "Walk me through what happens when I type a question"

```
User types question
  → detect_injection() — blocks jailbreak attempts
  → get_clock_string() — prepends current date/time to system prompt
  → similarity_search(k=8) — base context from ChromaDB
  → PRODUCT_SOURCE_MAP — if specific product + technical keyword:
      filtered similarity_search from that product's source docs only
  → _build_input() — assembles question + context + chat history
  → ReAct agent — may call tools (weather/search/execute_code/vision)
  → answer returned to frontend
```

---

## "What is PRODUCT_SOURCE_MAP and why does it exist?"

Sprint 5 failure: generic answers because ChromaDB returned random chunks across all 49 products.

Fix: if the question names a specific product AND uses a technical keyword (install/specs/maintenance), we **force-filter** the vectorstore to only chunks from that product's source documents.

Result: installation steps now come from the actual installation PDF, not a review about a different product.

---

## "How does the image upload work?"

```
User clicks 📷 → browser sends multipart/form-data to POST /upload-image
  → FastAPI reads file bytes
  → base64-encode → passed to sprint7/vision/tool.py
  → Step 1: YOLOv8 endpoint (if YOLO_ENDPOINT configured, conf >= 0.6)
  → Step 2: if YOLO low confidence → llama-4-maverick (NVIDIA NIM) analyzes image
  → Both paths → ChromaDB seat cover query by brand + bowl shape
  → Recommendation returned to frontend
```

---

## "What is the confidence threshold and why 0.6?"

YOLOv8 was trained on 3 brands: Aquapro, Montecarlo, Smart. Outside these, confidence drops. 0.6 is the point where we trust YOLO's label. Below that, we fall back to the general vision model (llama-4-maverick) which can describe any toilet even if it doesn't know the exact brand.

Kill switch: `ENABLE_NVIDIA_FALLBACK=0` disables NIM fallback entirely.

---

## "What model powers MAYA?"

- **Text agent**: `gpt-4o-mini` (OpenAI) — cost, latency, what professor specified
- **Vision fallback**: `llama-4-maverick` via NVIDIA NIM — free tier, multimodal
- **Pipeline mode** (optional, disabled by default):
  - Step 1: `deepseek-v3.2` reasons
  - Step 2: `gpt-4o-mini` generates
  - Step 3: `glm-4.7` reviews

---

## "How do you prevent hallucinations?"

1. System prompt: "Base your answer ONLY on the context provided"
2. PRODUCT_SOURCE_MAP forces context from the right document
3. Vision tool uses real ChromaDB queries — not model imagination
4. LangSmith traces show exactly what context was passed in for every call

---

## "How does clock awareness work?"

Two lines:
```python
from sprint7.clock.inject import get_clock_string
# prepended to system prompt every ask() call
```

Before Sprint 7, if you asked "what day is it?" MAYA had no idea. Now it answers correctly because the current date/time is injected into every prompt.

---

## "What is the MCP server?"

`mcp_server.py` runs as a standalone MCP (Model Context Protocol) server over fastmcp stdio. Six tools exposed:
- weather, web_search, query_products, generate_product_table, get_product_sentiment, execute_code

Any MCP-compatible client can connect. The tools MAYA uses internally are now reusable externally.

---

## "What is Graphify / the knowledge graph?"

Dev tool — not part of MAYA runtime. We ran it on our own codebase:
- 186 nodes, 236 edges, 23 communities
- Caught: liability radar and product query both hit the same vectorstore (not truly separate)

Helped us understand what we built. Not in production.

---

## "Why didn't you build multi-agent?"

Scope. LangGraph natively supports it — you'd add a router node and two sub-agents. Clean split: customer agent (product support), analyst agent (full data access), orchestrator (routes by role). That's Sprint 8.

---

## "What's the ChromaDB setup?"

- 1,100+ chunks from 49 Corona products
- Embedding model: `text-embedding-3-small` (OpenAI)
- Persistent directory: `./chroma_db`
- FTS5 full-text search on top

---

## "How does dual-mode auth work?"

Customer mode: default, no login.  
Analyst mode: type the secret keyword → modal appears → enter password → `sessionStorage` stores key → all subsequent requests tagged `analyst`.

System prompt switches entirely — analyst gets bullet-heavy analysis prompts, customer gets warm friendly prompts.

---

## "Show me the LangSmith trace"

Open `smith.langchain.com` → project `corona-toilet-reviews` → click most recent run → chain shows: ask → agent → tool calls → final answer. Each node shows input/output + timing.
