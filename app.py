from flask import Flask, render_template, request
from dotenv import load_dotenv
import os
from google import generativeai as genai

# Load API Key
load_dotenv()
genai.configure(api_key=os.getenv("GOOGLE_API_KEY"))

app = Flask(__name__)

# Using free audio-supported model
model = genai.GenerativeModel("gemini-2.0-flash")


@app.route("/", methods=["GET", "POST"])
def home():
    result = None

    if request.method == "POST":
        if "audio" not in request.files:
            return render_template("index.html", result="⚠ Please upload a file")

        audio_file = request.files["audio"]

        if audio_file.filename == "":
            return render_template("index.html", result="⚠ No file selected")

        audio_bytes = audio_file.read()

        prompt = """
You are NutriFit AI — an advanced medical and nutrition intelligence assistant trained 
to understand diet-related conversations between a dietician and a client.

You will receive a call recording. Your job is to:

1. Transcribe the audio clearly.
2. Analyze the conversation deeply and extract health-related insights.
3. Structure the final output in the following format (no empty sections):

**1. Conversation Transcript**
(Write the transcript in readable format.)

**2. Summary of Call**
(4-6 lines summarizing the conversation.)

**3. Key Health Concerns**
(List medical and lifestyle concerns mentioned.)

**4. Dietary Habits Observed**
(Identify eating patterns, cuisines, frequency, and problems.)

**5. Possible Allergies or Restrictions**
(If none mentioned, infer based on discussion.)

**6. Suggested Improvements**
(Give actionable and specific suggestions based on the call.)

**7. Personalized Nutrition Recommendation**
(Macro focus, diet type, hydration level, supplements if applicable.)

**8. Tone and Emotion Analysis**
(e.g., Confused, Motivated, Stressed, Confident.)

Make the output clinically useful, simple to read, and professional.
Avoid disclaimers unless necessary.
"""


        response = model.generate_content(
            [
                prompt,
                {
                    "mime_type": audio_file.content_type,
                    "data": audio_bytes
                }
            ]
        )

        result = response.text

    return render_template("index.html", result=result)


if __name__ == "__main__":
    app.run(debug=True)
