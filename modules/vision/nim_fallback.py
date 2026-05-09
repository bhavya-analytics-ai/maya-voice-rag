"""
sprint7/vision/nim_fallback.py
gpt-4o-mini vision fallback — used when YOLOv8 confidence < threshold.
Identifies toilet brand/style and gives photo coaching if image is unclear.
Uses the same OPENAI_API_KEY as the rest of the app — no extra credentials needed.
"""
import os
import base64
import json
import re
from openai import OpenAI


def _encode_image(image_bytes: bytes) -> str:
    return base64.b64encode(image_bytes).decode("utf-8")


def nim_analyze_toilet(image_bytes: bytes) -> dict:
    """
    Send image to gpt-4o-mini vision.
    Returns dict with keys: brand, model_guess, description, seat_cover_note, photo_tip
    Falls back to empty strings on error.
    """
    client = OpenAI(api_key=os.getenv("OPENAI_API_KEY", ""))
    b64 = _encode_image(image_bytes)

    prompt = (
        "You are a Corona (Colombia) toilet product expert with computer vision skills. "
        "Analyze this image of a toilet and identify:\n"
        "1. Brand — look for labels/logos. Known Corona brands: Aquapro, Montecarlo, Smart. If not a Corona toilet, say the brand you see or Unknown.\n"
        "2. Bowl shape: round or elongated\n"
        "3. Style: one-piece or two-piece\n"
        "4. Color\n"
        "5. If the image is blurry, too dark, at a bad angle, or otherwise unclear, give a specific photo_tip on how to retake it.\n\n"
        "Respond ONLY with valid JSON using these keys: "
        "brand (string), model_guess (string or null), bowl_shape (string), style (string), color (string), "
        "description (1 sentence summary), seat_cover_recommendation (string), photo_tip (string or null).\n"
        "If the image is clear and a brand is identifiable, set photo_tip to null."
    )

    try:
        response = client.chat.completions.create(
            model="gpt-4o-mini",
            messages=[
                {
                    "role": "user",
                    "content": [
                        {"type": "text", "text": prompt},
                        {
                            "type": "image_url",
                            "image_url": {
                                "url": f"data:image/jpeg;base64,{b64}",
                                "detail": "low",  # faster + cheaper for product ID
                            },
                        },
                    ],
                }
            ],
            max_tokens=400,
            temperature=0.1,
        )
        raw = response.choices[0].message.content.strip()
        # Strip markdown code fences if present
        raw = re.sub(r'^```(?:json)?\n?|```$', '', raw, flags=re.MULTILINE).strip()
        json_match = re.search(r'\{.*\}', raw, re.DOTALL)
        if json_match:
            return json.loads(json_match.group())
        return {"description": raw, "brand": "Unknown", "seat_cover_recommendation": "", "photo_tip": None}
    except Exception as e:
        return {"brand": "Unknown", "description": str(e), "seat_cover_recommendation": "", "photo_tip": None}
