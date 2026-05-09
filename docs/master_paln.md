MAYA Sprint 7 — Master Plan
VISION
Live-defense-grade chatbot. Image-aware. Time-aware. Multi-model verified. Professor types anything, MAYA answers correctly. Demo runs solo, no slides to hide behind.

SCOPE BOUNDARIES (don't drift)
No voice
No cross-session memory
No multi-agent
No new product data ingestion
Sprint 6 architecture stays intact — we layer, not rebuild
ARCHITECTURE (what's new on top of Sprint 6)
TEXT QUESTION ───► ReAct agent ───► [Sprint 6 tools + new vision tool] ───► answer
IMAGE UPLOAD ───► vision tool ───► YOLOv8 (yours) ──conf≥0.6──► detected brand
                              └── conf<0.6 ──► llama-4-maverick (NIM fallback)
                                              ──► detected brand + general toilet info
                              ──► ChromaDB lookup ──► matching seat cover/accessory recs
HARD QUESTION ───► [optional] pipeline mode ───► deepseek (reason) ─► gpt-4o-mini (draft) ─► glm-4.7 (review) ─► answer
PHASES (BUILD ORDER, LOCKED)
#	Phase	Days	Tool / Library	Notes
0	Clock injection in system prompt	0.1	none — 2 lines	Fix the Sprint 5 bug. Inject now() into prompt every ask() call
1	Vision tool — YOLOv8 + Maverick fallback	1	YOLOv8 (yours) + NVIDIA NIM	New @tool analyze_toilet_image(). Confidence threshold 0.6. Returns brand + source + recs
2	Image upload frontend	0.5	Port from Truman dashboard	Pill preview, loading state, inline result display
3	Accessory recommendation lookup	0.5	ChromaDB filter by detected brand	The end-to-end flow from the mockup chat
4	Pipeline mode (the "amazing")	1	LangGraph nodes + NVIDIA NIM	deepseek-v3.2 reasons → gpt-4o-mini generates → glm-4.7 reviews. Opt-in via flag
5	Code defense pass	1	none — docstrings + CODE_TOUR.md	Annotate every function. Write a one-pager cheat sheet for the demo
6	Pre-flight Q&A bulletproofing	1	manual test runner	30+ questions, all categories. Log failures. Fix. Save winning traces
7	Polish + dry run	0.5	none	Health check, pre-warm, backup screenshots, demo rehearsal
Total: ~5.6 days focused work. Fits alongside Truman v2 phase 0–1.

WHAT STAYS YOURS (don't outsource)
PRODUCT_SOURCE_MAP — Sprint 6 retrieval fix, the actual moat
Vision routing logic — YOLOv8 first, fallback decision, confidence threshold
Pipeline mode trigger conditions — when to escalate, when not to burn tokens
Demo question catalog — what you tested against, your safety net
System prompt persona — already done, don't touch
WHAT'S COMMODITY (swappable)
LangGraph create_react_agent — could swap to custom loop
ChromaDB — could swap to Qdrant
NVIDIA NIM endpoints — could swap to OpenRouter/Groq
YOLOv8 — could swap to any other vision model
gpt-4o-mini — could swap once prof's gpt-4o-mini req is gone
All abstracted behind tool interfaces. Swap any one piece without touching the rest.

KILL SWITCHES (env vars)
ENABLE_VISION=1            # turn off vision tool entirely if YOLOv8 endpoint dies
ENABLE_NVIDIA_FALLBACK=1   # use llama-4-maverick when YOLO confidence low
ENABLE_PIPELINE_MODE=0     # off by default. Opt-in via "/deep" or "verify" prefix
If anything breaks live, flip the flag. Rest of system runs.

RISK GATES (per new tool)
Vision tool wraps YOLOv8 call in try/except with 5s timeout. Falls back to maverick on any error.
Pipeline mode has hard token budget (3K total across 3 calls) before circuit-breaks back to single-model.
Image upload returns text error to chat if no toilet detected, never crashes the agent.
REHEARSAL FLOW (run before demo)
1. "What is the maintenance schedule for the Aluvia Plus?"
   → Sprint 6 PRODUCT_SOURCE_MAP still works (regression check)
2. [upload photo of Aquapro toilet]
   → YOLOv8 detects, recs Aquapro accessories (vision works, known brand)
3. [upload photo of Nyren toilet — NOT in YOLO training set]
   → YOLO confidence low → maverick fallback → general identification + recs (vision graceful degradation)
4. "What day is it today?"
   → Returns correct date (Sprint 5 bug fixed)
5. "Compare the water consumption and ADA compliance of all your toilets and tell me which is best for a small bathroom" (with /deep prefix)
   → Pipeline mode triggers, 3-model chain, visible in LangSmith (the "amazing")
6. "What models are powering you?"
   → Lists tools + models honestly (system question)
If any of those 6 fails, fix before demo.

RISKS + MITIGATIONS
Risk	Mitigation
YOLOv8 endpoint down on demo day	Maverick fallback always works; flag ENABLE_VISION=0 falls back to "please describe your toilet"
Prof asks about a product that's not Nyren/Aluvia	Pre-flight Q&A phase catches this. Test all 49 product names
Prof tests prompt injection	Already shielded in Sprint 6 with detect_injection. Re-verify in phase 6
Pipeline mode burns NIM rate limit live	Hard 3K token budget + opt-in only. Default off
Time question gives stale answer	Phase 0 injects datetime.now() every call. Verified in rehearsal step 4
Image upload breaks text flow	Image processing in separate code path, agent untouched
LangSmith dashboard slow on demo	Pre-load a known-good trace as backup tab
CODE DEFENSE PLAYBOOK
The "explain your code" requirement is highlighted yellow because it's the differentiator. Two parts:

Part 1: CODE_TOUR.md — written reference. Sections:

Why ReAct over RAG (one paragraph)
What PRODUCT_SOURCE_MAP does and why (5 bullets)
How vision routing works (the YOLO→Maverick fallback)
Why LangSmith env vars are at the top of app.py (specific gotcha)
What the 6 tools do (one line each)
Part 2: Mental model — memorize:

File:line for the hardest 5 functions
The PRODUCT_SOURCE_MAP dict by heart
The 3 ReAct phases and what each does
Why we use gpt-4o-mini vision for OCR but NIM Maverick for live vision (cost/speed)
The injection regex patterns (count: 8, examples: 2)
Prof points at random line → you say "that's where we [thing]" not "uhh let me see".

HARD LIMITS (honest)
gpt-4o-mini still required by prof for the agent — only Sprint 7 unlocks NIM for vision and pipeline mode
YOLOv8 only knows 3 brands — fallback handles the other 46 but won't be as confident
Live demo means no edits — whatever's deployed is what runs
Pre-flight testing can't cover every question — must trust ReAct generalization for the long tail
TOTAL COST
Sprint 6 cost: ~$0.05 per demo (gpt-4o-mini + embeddings)
Sprint 7 add: $0 (NIM is free, YOLOv8 is yours, pipeline mode opt-in)
Demo session: ~$0.10–0.20 total
Review this. Tell me:

Phase order good or do you want pipeline mode earlier/later?
Vision routing strategy — YOLO-first with maverick fallback, or maverick-first with YOLO confirmation?
Pipeline mode trigger — explicit /deep prefix, automatic on hard questions, or both?
Anything missing that you saw in Truman's playbook that should apply here?