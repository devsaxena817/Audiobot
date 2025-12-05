import streamlit as st
import google.generativeai as genai
import os
from reportlab.lib.pagesizes import letter
from reportlab.pdfgen import canvas
from io import BytesIO

# Configure Gemini Key
from dotenv import load_dotenv
import os
import google.generativeai as genai

# Load .env file
load_dotenv()

# Configure Gemini Key from environment variable
api_key = os.getenv("GEMINI_API_KEY")

if not api_key:
    raise Exception("❌ API Key not found! Ensure .env file exists and variable name is correct.")

genai.configure(api_key=api_key)


# Prompt for analysis
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


model = genai.GenerativeModel("gemini-2.5-flash")



def analyze_audio(file):
    audio_bytes = uploaded_audio.read()

    response = model.generate_content(
    [
        prompt,
        {
            "mime_type": uploaded_audio.type,  # streamlit auto-detects mime 
            "data": audio_bytes
        }
    ]
)

    return response.text.strip()


def create_pdf(text_content):
    buffer = BytesIO()
    c = canvas.Canvas(buffer, pagesize=letter)

    width, height = letter
    y = height - 50  # top margin
    line_height = 14

    for line in text_content.split("\n"):
        if y < 50:
            c.showPage()
            y = height - 50

        c.drawString(40, y, line)
        y -= line_height

    c.save()
    buffer.seek(0)
    return buffer


# Streamlit UI
st.title("NutriFit AI — Voice Call Analyzer")
st.write("Upload health consultation audio to generate an AI-powered structured report.")

uploaded_audio = st.file_uploader("Upload Call Recording", type=['mp3', 'wav', 'm4a'])

if uploaded_audio:
    with st.spinner("Analyzing audio... please wait ⏳"):
        result = analyze_audio(uploaded_audio)

    st.success("Analysis Complete ✔️")
    st.write(result)


    # Create PDF
    pdf_file = create_pdf(result)

    # Download Button
    st.download_button(
        label="📄 Download Structured Health Report (PDF)",
        data=pdf_file,
        file_name="NutriFit_AI_Report.pdf",
        mime="application/pdf"
    )
