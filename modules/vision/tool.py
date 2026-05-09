"""
sprint7/vision/tool.py
@tool analyze_toilet_image — registered in chatbot.py TOOLS list.

Flow:
  1. YOLOv8 (3-class: Aquapro, Montecarlo, Smart) → if conf >= 0.4: use label
  2. else: gpt-4o-mini vision → identify brand/style + photo coaching if unclear
  3. Map brand → known compatible Corona seat covers
  4. Return clean recommendation string
"""
import os
import base64
from langchain_core.tools import tool

ENABLE_VISION = os.getenv("ENABLE_VISION", "1") == "1"
ENABLE_VISION_FALLBACK = os.getenv("ENABLE_VISION_FALLBACK", "1") == "1"

# Hardcoded seat cover map — real product names from Corona catalog
SEAT_COVER_MAP = {
    "Aquapro":    ["Asiento Versátil RD (Ref. 959080001)", "Tapa Aquapro Blanco (Ref. 933505001)"],
    "Montecarlo": ["Asiento Montecarlo Blanco (Ref. 933600001)", "Asiento Versátil RD (Ref. 959080001)"],
    "Smart":      ["Asiento Smart Blanco (Ref. 933700001)", "Tapa tanque Smart (Ref. 933709991)"],
    "Unknown":    [],
}


def build_vision_tool(vectorstore=None):
    """Factory — returns the @tool. vectorstore kept for signature compat."""

    @tool
    def analyze_toilet_image(image_b64: str) -> str:
        """
        Analyze a base64-encoded toilet image.
        Identifies the toilet brand using YOLOv8 (trained on Aquapro, Montecarlo, Smart)
        and recommends matching Corona seat covers.
        Use this when the user uploads a photo of a toilet.
        """
        if not ENABLE_VISION:
            return "Vision analysis is currently disabled."

        image_bytes = base64.b64decode(image_b64)

        # Step 1 — YOLOv8
        brand, conf = None, 0.0
        try:
            from modules.vision.yolo_client import yolo_detect
            brand, conf = yolo_detect(image_bytes)
        except Exception:
            pass

        # Step 2 — gpt-4o-mini vision fallback if YOLO didn't fire
        vision_data = {}
        photo_tip = None
        if not brand and ENABLE_VISION_FALLBACK:
            try:
                from modules.vision.nim_fallback import nim_analyze_toilet
                vision_data = nim_analyze_toilet(image_bytes)
                detected = vision_data.get("brand")
                photo_tip = vision_data.get("photo_tip")
                if detected not in ("Unknown", "", None):
                    brand = detected
                    conf = 0.7  # GPT-4o-mini confidence placeholder
            except Exception:
                pass

        # Step 3 — Seat cover lookup
        seat_covers = SEAT_COVER_MAP.get(brand or "Unknown", [])

        # Step 4 — Compose response
        if brand and brand != "Unknown":
            if not seat_covers:
                # Brand detected but not in our map — return explicit signal, don't let LLM invent names
                return (
                    f"detected_brand={brand} confidence={conf:.0%}\n"
                    f"no_covers_mapped"
                )
            covers_text = "\n".join(f"  • {c}" for c in seat_covers)
            bowl = vision_data.get("bowl_shape", "")
            style = vision_data.get("style", "")
            extra = f" ({bowl}, {style})" if bowl and style else ""
            return (
                f"detected_brand={brand}{extra} confidence={conf:.0%}\n"
                f"Compatible Corona seat covers for {brand}:\n{covers_text}"
            )
        else:
            # Photo coaching if gpt-4o-mini gave a tip
            if photo_tip:
                return f"photo_tip={photo_tip}\nbrand=Unknown no_detection"
            desc = vision_data.get("description", "")
            if desc:
                return f"vision_description={desc}\nbrand=Unknown"
            return "brand=Unknown no_detection"

    return analyze_toilet_image
