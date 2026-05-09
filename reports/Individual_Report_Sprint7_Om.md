**Individual Report – Sprint 7**
Team: 1
Student Name: Bhavya Pandya

---

**OpenAI Realtime Voice Integration and AI Chatbot Architecture**

---

**Role in Sprint Activities**

In Sprint 7, I was responsible for the overall system architecture and the integration of the OpenAI Realtime API into the MAYA chatbot. My role covered the FastAPI backend, the WebSocket voice bridge, the LangGraph ReAct agent upgrades, and resolving critical environment and authentication issues that blocked the voice pipeline. I also replaced the web search tool with Tavily and coordinated the removal of analyst mode to simplify the system for production use.

---

**Architecture and Technical Overview**

The core of Sprint 7 was upgrading MAYA from a text-only chatbot into a multimodal system with real-time voice, computer vision, and smarter web search. The system runs three services: MAYA on FastAPI (port 8000), a YOLO inference server (port 8001), and an ngrok tunnel for public access.

The voice pipeline works as follows: the browser captures microphone audio via getUserMedia with echo cancellation enabled, downsamples it from 48kHz Float32 to 24kHz PCM16, and streams raw audio bytes over a WebSocket to the /ws/voice endpoint on the FastAPI server. The server forwards the audio to the OpenAI Realtime API (gpt-4o-mini-realtime-preview) over a secure WebSocket connection. Server-side VAD (threshold=0.82, silence=500ms) handles turn detection. Tool calls from the Realtime API are resolved server-side — the FastAPI bridge dispatches web_search, get_weather, query_products, and execute_code, then injects results back into the conversation before triggering a new response. Audio deltas are streamed back to the browser and played via AudioContext with gapless scheduling. Barge-in is handled by flushing queued audio on speech_started events.

A critical environment issue was identified and fixed: the shell environment (via ~/.zshrc) had an old OPENAI_API_KEY export that was silently overriding the correct key in .env. Python-dotenv does not override existing shell variables by default. The fix was changing load_dotenv() to load_dotenv(override=True) in app.py, ensuring .env always takes precedence.

The web search tool was upgraded from DuckDuckGo to Tavily with search_depth="advanced" and include_answer=True, which generates a synthesized direct answer rather than raw snippets. Context injection was added for short or ambiguous queries — the previous user message and today's date are prepended before hitting Tavily so queries like "who won?" resolve correctly.

---

**Challenges Encountered**

The most significant challenge was diagnosing the insufficient_quota error on the Realtime API. The error appeared despite a valid API key with sufficient balance. Multiple isolation tests confirmed the key and payload worked correctly in standalone scripts. The root cause was traced to a stale OPENAI_API_KEY export in ~/.zshrc that had been set months earlier and was silently overriding the .env value at process startup. This was a non-obvious environment layering issue that required systematic elimination of all other possible causes before the shell variable was identified.

Another challenge was browser microphone permissions. Chrome blocks getUserMedia on plain HTTP, which prevented the voice tab from working over the local network. This was resolved by generating a self-signed SSL certificate and running uvicorn with --ssl-keyfile and --ssl-certfile flags, allowing the voice tab to be served over HTTPS.

---

**Major Contributions**

- Designed and implemented the FastAPI WebSocket bridge (/ws/voice) connecting the browser to the OpenAI Realtime API
- Integrated server-side VAD with tuned threshold and silence parameters for natural conversation feel
- Implemented server-side tool dispatch for voice (web_search, get_weather, query_products, execute_code)
- Diagnosed and fixed the load_dotenv(override=True) environment bug that blocked the entire voice pipeline
- Upgraded web_search tool from DuckDuckGo to Tavily with direct answer synthesis
- Added context injection for short/ambiguous search queries using conversation memory and current date
- Removed analyst mode entirely from chatbot.py, app.py, and index.html
- Generated self-signed SSL certificate for HTTPS localhost to enable browser mic permissions
- Injected full CORONA_KNOWLEDGE into the Realtime API voice system prompt
- Added voice tab link to the main chat UI header

---

**Newly Acquired Knowledge**

Through this sprint, I gained hands-on experience with the OpenAI Realtime API and its WebSocket protocol, including session configuration, server VAD, tool call handling, and audio streaming. I learned how PCM16 audio works at the byte level and how to build a low-latency browser-to-server-to-API audio pipeline with barge-in support.

I also developed a deeper understanding of Python environment variable precedence — specifically how shell exports interact with python-dotenv and how to debug silent key overrides. This was a non-trivial operational issue that required understanding the full process startup chain. Additionally, I gained practical experience with browser security constraints around microphone access and how to serve local development servers over HTTPS to bypass getUserMedia restrictions.
