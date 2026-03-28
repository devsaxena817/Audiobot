import os
import re
import json
import uuid
import logging
from flask import Flask, render_template, request, jsonify, send_from_directory
from dotenv import load_dotenv
from google import generativeai as genai
from reportlab.lib.pagesizes import letter
from reportlab.pdfgen import canvas

# Load env
load_dotenv()
API_KEY = os.getenv("GOOGLE_API_KEY")
if not API_KEY:
    raise RuntimeError("Please set GOOGLE_API_KEY in your .env")

genai.configure(api_key=API_KEY)

# Choose model (flash - cheaper / available)
MODEL_NAME = "gemini-2.0-flash"
model = genai.GenerativeModel(MODEL_NAME)

app = Flask(__name__, static_folder="static", template_folder="templates")
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(name)s: %(message)s"
)
app.logger.setLevel(logging.INFO)

# Folder to store generated PDFs
REPORTS_DIR = os.path.join(app.static_folder, "reports")
os.makedirs(REPORTS_DIR, exist_ok=True)


DUAL_PROMPT = r"""
You are NutriFit AI — an advanced medical & nutrition intelligence assistant that analyzes dietician-client voice consultations.

TASK:
1) Transcribe the audio.
2) Extract structured health & diet insights.
3) Return two parts in this exact order:

PART A — JSON ONLY (MANDATORY, parseable):
Return a single JSON object with these keys exactly:
{
  "transcript": "full transcription string",
  "summary": "short 4-6 line summary",
  "key_health_concerns": [{"label":"string","evidence":"text excerpt","confidence":0.0}],
  "dietary_habits": [{"label":"string","details":"text","confidence":0.0}],
  "allergies_or_restrictions": [{"label":"string","evidence":"text","confidence":0.0}],
  "suggested_improvements": ["action item 1","action item 2"],
  "personalized_nutrition": {
      "calorie_target": "e.g. 1800 kcal/day or null",
      "macro_split": {"protein_pct":30,"carb_pct":45,"fat_pct":25},
      "sample_meal_plan": ["Breakfast: ...","Lunch: ..."],
      "hydration_l_per_day": 2.5,
      "supplements": ["name - reason"]
  },
  "tone_emotion": {"primary":"Stressed","secondary":["Anxious"], "confidence":0.0},
  "follow_up_questions": ["question 1","question 2"],
  "metadata": {"duration_seconds": null, "speaker_segments": [], "confidence_overall":0.0}
}

Important rules:
- JSON must be valid JSON only (no backticks, no explanation before it). If any field is unknown use null / [] / "".
- Confidence fields are floats 0.0–1.0.

PART B — HUMAN-READABLE REPORT (after the JSON):
Provide a concise professional report using the same headings. Keep it scannable.

END.
"""


def call_model_with_audio(audio_bytes: bytes, mime_type: str, prompt: str) -> str:
    """
    Call Gemini generate_content with audio bytes and return raw text response.
    """
    app.logger.info(
        "Calling Gemini model=%s mime_type=%s audio_bytes=%s",
        MODEL_NAME,
        mime_type,
        len(audio_bytes),
    )
    response = model.generate_content(
        [
            prompt,
            {"mime_type": mime_type, "data": audio_bytes}
        ]
    )
    return response.text


def extract_first_json(text: str):
    """
    Extract the first JSON object from model output robustly using recursion-capable regex.
    Returns Python object or None.
    """
    # Try a regex using balanced-braces via recursion if supported
    # Fallback simpler approach if regex engine doesn't support recursion
    # We'll search for the first '{' and then attempt to parse progressively until valid JSON parsed.
    start = text.find("{")
    if start == -1:
        return None, text

    # Try to find a matching closing bracket by expanding
    for end in range(start + 1, len(text)):
        candidate = text[start:end + 1]
        try:
            parsed = json.loads(candidate)
            # success
            remainder = text[end + 1:].strip()
            return parsed, remainder
        except Exception:
            continue

    # As fallback, try to find a block using a looser regex (may fail on nested)
    m = re.search(r'(\{(?:[^{}]|\{[^{}]*\})*\})', text, flags=re.DOTALL)
    if m:
        raw = m.group(1)
        try:
            return json.loads(raw), (text.replace(raw, "", 1).strip())
        except Exception:
            return None, text

    return None, text


def validate_json_schema(j: dict) -> bool:
    """
    Minimal validation: ensure essential keys exist.
    """
    required = ["transcript", "summary", "personalized_nutrition"]
    return all(k in j for k in required)


def create_pdf_from_json(j: dict, filename: str):
    """
    Create a readable PDF from structured JSON.
    """
    path = os.path.join(REPORTS_DIR, filename)
    c = canvas.Canvas(path, pagesize=letter)
    width, height = letter

    margin_x = 40
    y = height - 50
    line_h = 14

    c.setFont("Helvetica-Bold", 16)
    c.drawString(margin_x, y, "NutriFit AI - Consultation Report")
    y -= 28

    c.setFont("Helvetica-Bold", 12)
    c.drawString(margin_x, y, "Summary:")
    y -= line_h
    c.setFont("Helvetica", 11)
    for ln in (j.get("summary") or "").splitlines():
        if y < 60:
            c.showPage()
            y = height - 50
        c.drawString(margin_x, y, ln)
        y -= line_h

    # Helper to draw a section
    def draw_section(title, content_lines):
        nonlocal y
        if y < 80:
            c.showPage()
            y = height - 50
        c.setFont("Helvetica-Bold", 12)
        c.drawString(margin_x, y, title)
        y -= line_h
        c.setFont("Helvetica", 11)
        for line in content_lines:
            if y < 60:
                c.showPage()
                y = height - 50
            c.drawString(margin_x + 6, y, "- " + line)
            y -= line_h

    # Key health concerns
    kh = []
    for item in j.get("key_health_concerns", []):
        lab = item.get("label", "")
        ev = item.get("evidence", "")
        kh.append(f"{lab} — {ev} (conf: {item.get('confidence',0):.2f})")
    if kh:
        draw_section("Key Health Concerns", kh)

    # Dietary habits
    dh = []
    for item in j.get("dietary_habits", []):
        dh.append(f"{item.get('label','')}: {item.get('details','')} (conf: {item.get('confidence',0):.2f})")
    if dh:
        draw_section("Dietary Habits", dh)

    # Suggestions
    sug = j.get("suggested_improvements", [])
    if sug:
        draw_section("Suggested Improvements", sug)

    # Personalized nutrition
    pn = j.get("personalized_nutrition", {})
    p_lines = []
    p_lines.append(f"Calorie target: {pn.get('calorie_target') or 'N/A'}")
    ms = pn.get("macro_split") or {}
    p_lines.append(f"Macro split: P {ms.get('protein_pct','-')}% | C {ms.get('carb_pct','-')}% | F {ms.get('fat_pct','-')}%")
    if pn.get("hydration_l_per_day"):
        p_lines.append(f"Hydration: {pn.get('hydration_l_per_day')} L/day")
    for meal in pn.get("sample_meal_plan", []):
        p_lines.append(meal)
    if pn.get("supplements"):
        p_lines.append("Supplements: " + ", ".join(pn.get("supplements")))
    draw_section("Personalized Nutrition", p_lines)

    c.save()
    return path


@app.route("/", methods=["GET"])
def index():
    return render_template("index.html")


@app.route("/process", methods=["POST"])
def process():
    """
    Receives an audio file (form-data key: audio), calls Gemini, returns parsed JSON + human report.
    """
    f = request.files.get("audio")
    if not f:
        app.logger.warning("Process request rejected: no audio file received")
        return jsonify({"error": "No audio file received"}), 400

    app.logger.info(
        "Received audio upload filename=%s content_type=%s content_length=%s",
        f.filename,
        f.content_type,
        request.content_length,
    )
    audio_bytes = f.read()
    mime_type = f.content_type or "audio/wav"

    # Call model
    try:
        raw = call_model_with_audio(audio_bytes, mime_type, DUAL_PROMPT)
    except Exception as e:
        app.logger.exception(
            "Gemini model call failed for filename=%s mime_type=%s",
            f.filename,
            mime_type,
        )
        return jsonify({
            "error": "Model call failed",
            "details": str(e),
            "exception_type": e.__class__.__name__,
        }), 500

    # Extract JSON
    parsed_json, remainder = extract_first_json(raw)
    if parsed_json is None:
        # Return raw for debugging
        app.logger.error(
            "Could not extract JSON from model output for filename=%s raw_preview=%r",
            f.filename,
            raw[:1000],
        )
        return jsonify({"error": "Could not extract JSON from model output", "raw": raw}), 500

    # Minimal validation
    if not validate_json_schema(parsed_json):
        # still continue but flagged
        app.logger.warning(
            "Parsed JSON missing required keys for filename=%s keys=%s",
            f.filename,
            sorted(parsed_json.keys()),
        )
        parsed_json["_validation_warning"] = "Missing required top-level keys"

    # Create PDF and return URL
    pdf_filename = f"NutriFit_Report_{uuid.uuid4().hex[:8]}.pdf"
    try:
        pdf_path = create_pdf_from_json(parsed_json, pdf_filename)
        pdf_url = f"/static/reports/{pdf_filename}"
    except Exception as e:
        app.logger.exception(
            "PDF generation failed for filename=%s pdf_filename=%s",
            f.filename,
            pdf_filename,
        )
        pdf_url = None

    app.logger.info(
        "Process request completed filename=%s pdf_created=%s",
        f.filename,
        bool(pdf_url),
    )
    return jsonify({
        "json": parsed_json,
        "report_text": remainder.strip() or raw,
        "pdf_url": pdf_url
    })


@app.route("/download_report/<filename>", methods=["GET"])
def download_report(filename):
    # Serve from static/reports
    return send_from_directory(REPORTS_DIR, filename, as_attachment=True)


@app.errorhandler(Exception)
def handle_unexpected_error(error):
    app.logger.exception("Unhandled server error during %s %s", request.method, request.path)
    return jsonify({
        "error": "Internal server error",
        "details": str(error),
        "exception_type": error.__class__.__name__,
    }), 500


if __name__ == "__main__":
    app.run(debug=True)
