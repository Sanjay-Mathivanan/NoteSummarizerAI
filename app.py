from flask import Flask, render_template, request, send_file
from summarizer import summarize_text, SummaryType
from fpdf import FPDF
import docx

app = Flask(__name__)
app.secret_key = "supersecret"

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

        if uploaded_file and uploaded_file.filename.endswith(".docx"):
            doc = docx.Document(uploaded_file)
            input_text = "\n".join([para.text for para in doc.paragraphs])
        elif uploaded_file and uploaded_file.filename.endswith(".txt"):
            input_text = uploaded_file.read().decode("utf-8")

        length_map = {
            "Short": (30, 80),
            "Medium": (80, 150),
            "Long": (150, 300)
        }
        min_len, max_len = length_map.get(selected_length, (80, 150))

        if input_text.strip():
            summary = summarize_text(input_text, min_len, max_len, selected_summary_type)

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
        pdf.multi_cell(0, 10, line.replace('•', '-').strip(), 0, 'L')

    path = "summary_temp.pdf"
    pdf.output(path)
    return send_file(path, as_attachment=True, download_name="summary.pdf")

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
