import os
import io
import re
import requests
import fitz  # PyMuPDF
from dotenv import load_dotenv
from flask import Flask, render_template, request, send_file
from summarizer import summarize_text, SummaryType
from fpdf import FPDF
import docx

# Load env variables from .env
load_dotenv()

app = Flask(__name__)
app.secret_key = os.getenv("FLASK_SECRET_KEY", "supersecret-default-fallback")

def translate_text(text, src="auto", dest="en"):
    if not text.strip():
        return ""
    # Split by paragraphs or chunks of ~2000 chars
    max_chunk = 2000
    chunks = []
    current_chunk = []
    current_len = 0
    for line in text.split('\n'):
        if current_len + len(line) + 1 > max_chunk:
            chunks.append('\n'.join(current_chunk))
            current_chunk = [line]
            current_len = len(line)
        else:
            current_chunk.append(line)
            current_len += len(line) + 1
    if current_chunk:
        chunks.append('\n'.join(current_chunk))
        
    translated_chunks = []
    for chunk in chunks:
        if not chunk.strip():
            continue
        try:
            url = "https://translate.googleapis.com/translate_a/single"
            params = {
                "client": "gtx",
                "sl": src,
                "tl": dest,
                "dt": "t",
                "q": chunk
            }
            r = requests.get(url, params=params, timeout=10)
            r.raise_for_status()
            res = r.json()
            translated_chunk = "".join([segment[0] for segment in res[0] if segment[0]])
            translated_chunks.append(translated_chunk)
        except Exception as e:
            # Fallback to original chunk if translation fails
            translated_chunks.append(chunk)
    return '\n'.join(translated_chunks)

def clean_text_for_pdf(text):
    # Remove HTML tags (e.g., <b>, </b>, <br>)
    text_clean = re.sub(r'<[^>]+>', '', text)
    
    # Replace common characters that might be problematic or have basic equivalents
    replacements = {
        '📝': '',
        '•': '-',
        '’': "'",
        '‘': "'",
        '”': '"',
        '“': '"',
        '—': '-',
        '–': '-',
    }
    for orig, rep in replacements.items():
        text_clean = text_clean.replace(orig, rep)
        
    # Safe encoding to latin-1 (ignore any un-encodable characters)
    return text_clean.encode('latin-1', errors='ignore').decode('latin-1')

@app.route("/")
def home():
    return render_template("index.html")

@app.route("/summarize", methods=["GET", "POST"])
def summarize():
    summary = ""
    input_text = ""
    selected_summary_type = "Paragraph"
    selected_language = "English"
    selected_length = "Medium"

    if request.method == "POST":
        input_text = request.form.get("noteText", "")
        uploaded_file = request.files.get("file")

        selected_summary_type = request.form.get("summaryType", "Paragraph")
        selected_language = request.form.get("language", "English")
        selected_length = request.form.get("length", "Medium")

        if uploaded_file and uploaded_file.filename != "":
            if uploaded_file.filename.endswith(".docx"):
                try:
                    doc = docx.Document(uploaded_file)
                    input_text = "\n".join([para.text for para in doc.paragraphs])
                except Exception as e:
                    input_text = f"Error reading DOCX: {e}"
            elif uploaded_file.filename.endswith(".txt"):
                try:
                    input_text = uploaded_file.read().decode("utf-8")
                except Exception as e:
                    input_text = f"Error reading TXT: {e}"
            elif uploaded_file.filename.endswith(".pdf"):
                try:
                    pdf_data = uploaded_file.read()
                    pdf_doc = fitz.open(stream=pdf_data, filetype="pdf")
                    pdf_text_parts = []
                    for page in pdf_doc:
                        page_text = page.get_text()
                        if page_text:
                            pdf_text_parts.append(page_text)
                    input_text = "\n".join(pdf_text_parts)
                except Exception as e:
                    input_text = f"Error reading PDF: {e}"

        length_map = {
            "Short": (30, 80),
            "Medium": (80, 150),
            "Long": (150, 300)
        }
        min_len, max_len = length_map.get(selected_length, (80, 150))

        if input_text.strip() and not (input_text.startswith("Error reading PDF") or 
                                       input_text.startswith("Error reading DOCX") or 
                                       input_text.startswith("Error reading TXT")):
            # Map selected language to Google Translate codes
            lang_map = {
                "Tamil": "ta",
                "Hindi": "hi"
            }
            target_lang = lang_map.get(selected_language)

            processing_text = input_text
            # If target language is Hindi or Tamil, translate the input text to English first
            if target_lang:
                processing_text = translate_text(input_text, src="auto", dest="en")

            # Summarize in English
            summary_en = summarize_text(processing_text, min_len, max_len, selected_summary_type)

            # If target language is Hindi or Tamil, translate the English summary back
            if target_lang and not summary_en.startswith("⚠️ Error summarizing"):
                summary = translate_text(summary_en, src="en", dest=target_lang)
            else:
                summary = summary_en

    return render_template("summarize.html",
                           summary=summary,
                           input_text=input_text,
                           selected_summary_type=selected_summary_type,
                           selected_language=selected_language,
                           selected_length=selected_length)

@app.route("/download_pdf", methods=["POST"])
def download_pdf():
    summary_text = request.form.get("summary_text", "No summary available.")
    pdf = FPDF()
    pdf.add_page()
    pdf.set_font("Arial", size=12)

    for line in summary_text.split('<br>'):
        cleaned_line = clean_text_for_pdf(line).strip()
        if cleaned_line:
            pdf.multi_cell(0, 10, cleaned_line, 0, 'L')

    # Output to memory string, encode to latin-1 bytes
    pdf_string = pdf.output(dest='S')
    pdf_bytes = pdf_string.encode('latin-1')

    # Send the memory stream directly
    return send_file(
        io.BytesIO(pdf_bytes),
        mimetype='application/pdf',
        as_attachment=True,
        download_name="summary.pdf"
    )

@app.route("/about")
def about():
    return render_template("about.html")

@app.route("/contact")
def contact():
    return render_template("contact.html")

@app.route("/privacy")
def privacy():
    return render_template("privacy.html")

if __name__ == "__main__":
    app.run(debug=True)
