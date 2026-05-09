"""
sprint7/pipeline/orchestrator.py
3-model pipeline: deepseek-v3.2 reasons → gpt-4o-mini generates → glm-4.7 reviews.
Explicit opt-in only (never auto). Triggered by ENABLE_PIPELINE_MODE env or per-call flag.

Requires NVIDIA_API_KEY for deepseek + glm, OPENAI_API_KEY for gpt-4o-mini.
"""
import os
from openai import OpenAI

NIM_BASE_URL = "https://integrate.api.nvidia.com/v1"
NIM_KEY      = os.getenv("NVIDIA_API_KEY", "")
OAI_KEY      = os.getenv("OPENAI_API_KEY", "")

ENABLE_PIPELINE_MODE = os.getenv("ENABLE_PIPELINE_MODE", "0") == "1"

STEP1_MODEL = "deepseek-ai/deepseek-v3"            # reasoner
STEP2_MODEL = "gpt-4o-mini"                         # generator (OpenAI)
STEP3_MODEL = "zhipuai/glm-4-9b-chat"               # reviewer


def _nim_client() -> OpenAI:
    return OpenAI(api_key=NIM_KEY, base_url=NIM_BASE_URL)


def _oai_client() -> OpenAI:
    return OpenAI(api_key=OAI_KEY)


def run_pipeline(question: str, context: str, role: str = "customer") -> str:
    """
    3-step pipeline. Returns final polished answer string.
    Raises RuntimeError if pipeline is disabled.
    """
    if not ENABLE_PIPELINE_MODE:
        raise RuntimeError("Pipeline mode is disabled. Set ENABLE_PIPELINE_MODE=1 to enable.")

    nim = _nim_client()
    oai = _oai_client()

    # ── Step 1: deepseek reasons ──────────────────────────────────────────────
    reason_prompt = (
        f"You are a reasoning engine. Given the question and context below, "
        f"produce a structured reasoning plan: key facts, gaps, answer approach. "
        f"Do NOT write the final answer yet.\n\n"
        f"Context:\n{context}\n\nQuestion: {question}"
    )
    step1 = nim.chat.completions.create(
        model=STEP1_MODEL,
        messages=[{"role": "user", "content": reason_prompt}],
        max_tokens=500,
        temperature=0.1,
    )
    reasoning = step1.choices[0].message.content.strip()

    # ── Step 2: gpt-4o-mini generates ────────────────────────────────────────
    tone = "warm, friendly, emoji-rich" if role == "customer" else "direct, analytical, bullet-heavy"
    gen_prompt = (
        f"Using this reasoning:\n{reasoning}\n\n"
        f"And this context:\n{context}\n\n"
        f"Write a {tone} answer to: {question}\n"
        f"Be concise, accurate, and helpful."
    )
    step2 = oai.chat.completions.create(
        model=STEP2_MODEL,
        messages=[{"role": "user", "content": gen_prompt}],
        max_tokens=600,
        temperature=0.4,
    )
    draft = step2.choices[0].message.content.strip()

    # ── Step 3: glm-4.7 reviews ───────────────────────────────────────────────
    review_prompt = (
        f"Review this draft answer for accuracy, tone, and completeness. "
        f"Fix any errors. Output only the final polished answer — no meta-commentary.\n\n"
        f"Original question: {question}\n\nDraft:\n{draft}"
    )
    step3 = nim.chat.completions.create(
        model=STEP3_MODEL,
        messages=[{"role": "user", "content": review_prompt}],
        max_tokens=600,
        temperature=0.2,
    )
    final = step3.choices[0].message.content.strip()
    return final
