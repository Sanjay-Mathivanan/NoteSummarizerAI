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
from werkzeug.utils import secure_filename

# Load env variables from .env
load_dotenv()

app = Flask(__name__)
# Load key from env, falling back to a secure default if undefined
app.secret_key = os.getenv("FLASK_SECRET_KEY", "prod-fallback-secure-key-928471")

ALLOWED_EXTENSIONS = {"txt", "pdf", "docx"}

def allowed_file(filename):
    return "." in filename and filename.rsplit(".", 1)[1].lower() in ALLOWED_EXTENSIONS

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

@app.route("/debug-dns")
def debug_dns():
    import socket
    import subprocess
    results = {}
    
    # 1. Try socket.gethostbyname for Hugging Face
    try:
        results["gethostbyname_hf"] = socket.gethostbyname("router.huggingface.co")
    except Exception as e:
        results["gethostbyname_hf"] = f"Error: {e}"
        
    # 2. Try socket.gethostbyname for Google
    try:
        results["gethostbyname_google"] = socket.gethostbyname("google.com")
    except Exception as e:
        results["gethostbyname_google"] = f"Error: {e}"
        
    # 3. Try running nslookup for Hugging Face
    try:
        res = subprocess.run(["nslookup", "router.huggingface.co"], capture_output=True, text=True, timeout=5)
        results["nslookup_hf"] = f"STDOUT:\n{res.stdout}\nSTDERR:\n{res.stderr}"
    except Exception as e:
        results["nslookup_hf"] = f"Error: {e}"
        
    # 4. Try running curl to Hugging Face status or API URL
    try:
        res = subprocess.run(["curl", "-I", "https://router.huggingface.co"], capture_output=True, text=True, timeout=5)
        results["curl_hf"] = f"STDOUT:\n{res.stdout}\nSTDERR:\n{res.stderr}"
    except Exception as e:
        results["curl_hf"] = f"Error: {e}"
        
    return results

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

        # Handle file upload validation and parsing
        if uploaded_file and uploaded_file.filename != "":
            if not allowed_file(uploaded_file.filename):
                input_text = "Error: Unsupported file format. Please upload only .txt, .docx, or .pdf files."
            else:
                filename = secure_filename(uploaded_file.filename)
                if filename.endswith(".docx"):
                    try:
                        doc = docx.Document(uploaded_file)
                        input_text = "\n".join([para.text for para in doc.paragraphs])
                    except Exception as e:
                        input_text = f"Error reading DOCX: {e}"
                elif filename.endswith(".txt"):
                    try:
                        input_text = uploaded_file.read().decode("utf-8")
                    except Exception as e:
                        input_text = f"Error reading TXT: {e}"
                elif filename.endswith(".pdf"):
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

        # Check if input text is valid and has no parser errors
        if input_text.strip() and not input_text.startswith("Error"):
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
            if target_lang and not summary_en.startswith("⚠️"):
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

if __name__ == "__main__":
    # Render binds dynamically to the PORT environment variable
    port = int(os.getenv("PORT", 5000))
    app.run(host="0.0.0.0", port=port, debug=False)
