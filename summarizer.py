import os
import requests
import time
from enum import Enum

# Hugging Face Inference API configuration
HF_API_KEY = os.getenv("HF_API_KEY", "")
API_URL = "https://router.huggingface.co/hf-inference/models/facebook/bart-large-cnn"

# Try importing transformers locally for development fallback
try:
    from transformers import pipeline
    HAS_LOCAL_MODEL = True
except ImportError:
    HAS_LOCAL_MODEL = False

local_summarizer = None

def get_local_summarizer():
    global local_summarizer
    if local_summarizer is None and HAS_LOCAL_MODEL:
        print("Loading local summarizer model (fallback)...")
        # Load the model locally using CPU
        local_summarizer = pipeline("summarization", model="facebook/bart-large-cnn")
    return local_summarizer

def query_inference_api(text, min_len, max_len):
    # If no API key is set and local fallback is available, use the local model directly
    if not HF_API_KEY and HAS_LOCAL_MODEL:
        try:
            model = get_local_summarizer()
            if model:
                print("Running summarization locally...")
                result = model(text, min_length=int(min_len), max_length=int(max_len), do_sample=False)
                return result[0]["summary_text"]
        except Exception as local_err:
            return f"⚠️ Local fallback error: {local_err}"

    headers = {"Authorization": f"Bearer {HF_API_KEY}"} if HF_API_KEY else {}
    payload = {
        "inputs": text,
        "parameters": {
            "min_length": int(min_len),
            "max_length": int(max_len),
            "do_sample": False
        }
    }

    max_retries = 3
    for attempt in range(max_retries):
        try:
            response = requests.post(API_URL, headers=headers, json=payload, timeout=15)
            
            # Handle backend model loading status (HTTP 503)
            if response.status_code == 503:
                data = response.json()
                est_time = data.get("estimated_time", 20)
                if attempt < max_retries - 1:
                    print(f"Model is booting (503). Retrying in {min(est_time, 10)} seconds...")
                    time.sleep(min(est_time, 10))
                    continue
                return f"⚠️ Hugging Face model is currently booting up. Please try again in {int(est_time)} seconds."
                
            response.raise_for_status()
            data = response.json()
            
            if isinstance(data, list) and len(data) > 0 and "summary_text" in data[0]:
                return data[0]["summary_text"]
            else:
                return f"⚠️ Unexpected response from Hugging Face: {data}"
                
        except requests.exceptions.Timeout as timeout_err:
            print(f"Attempt {attempt + 1} failed (Timeout): {timeout_err}")
            if attempt < max_retries - 1:
                time.sleep(4)
                continue
            if HAS_LOCAL_MODEL:
                try:
                    print("All API retries timed out. Falling back to local model...")
                    model = get_local_summarizer()
                    if model:
                        result = model(text, min_length=int(min_len), max_length=int(max_len), do_sample=False)
                        return result[0]["summary_text"]
                except Exception as local_err:
                    return f"⚠️ Local fallback error: {local_err}"
            return f"⚠️ Connection Timeout: The Hugging Face API took too long to respond. Please try again."
            
        except requests.exceptions.ConnectionError as conn_err:
            print(f"Attempt {attempt + 1} failed (Connection): {conn_err}")
            if attempt < max_retries - 1:
                time.sleep(2)
                continue
            if HAS_LOCAL_MODEL:
                try:
                    print("All API retries failed. Falling back to local model...")
                    model = get_local_summarizer()
                    if model:
                        result = model(text, min_length=int(min_len), max_length=int(max_len), do_sample=False)
                        return result[0]["summary_text"]
                except Exception as local_err:
                    return f"⚠️ Local fallback error: {local_err}"
            return f"⚠️ Connection Error: {conn_err}. Please verify your internet connection or configure local environment variables."
        except Exception as e:
            return f"⚠️ API Error: {e}"

# Split text into chunks
def split_into_chunks(text, max_words=800):
    words = text.split()
    return [' '.join(words[i:i + max_words]) for i in range(0, len(words), max_words)]

# Structured formatting: Bullet Points
def format_bullet(text):
    lines = text.split('. ')
    formatted = [f"• {line.strip()}" for line in lines if line.strip()]
    return '<b>📝 Bullet Points:</b><br>' + '<br>'.join(formatted)

# Structured formatting: Outline (Advanced)
def format_outline(text):
    sections = text.split('. ')
    output = []
    roman_numerals = ['I', 'II', 'III', 'IV', 'V', 'VI']
    letter = 'A'
    index = 0

    for i, sec in enumerate(sections):
        sec = sec.strip()
        if not sec:
            continue
        if i % 4 == 0:
            output.append(f"<b>{roman_numerals[index % len(roman_numerals)]}. {sec}</b>")
            letter = 'A'
            index += 1
        else:
            output.append(f"{letter}. {sec}")
            letter = chr(ord(letter) + 1)
    return '<br>'.join(output)

# Enum with multiple summary formats
class SummaryType(Enum):
    PARAGRAPH = ("Paragraph", lambda text: text)
    BULLET_POINTS = ("Bullet Points", format_bullet)
    STRUCTURED_NOTES = ("Structured Notes", format_bullet)  # Alias for now
    OUTLINE = ("Outline", format_outline)

    def __init__(self, label, formatter):
        self.label = label
        self.formatter = formatter

    def format(self, text):
        return self.formatter(text)

    @classmethod
    def choices(cls):
        return [(member.name, member.label) for member in cls]

# Main summarization function
def summarize_text(text, min_len=30, max_len=100, summary_type="Paragraph"):
    MAX_WORDS = 10000
    words = text.split()
    if len(words) > MAX_WORDS:
        text = ' '.join(words[:MAX_WORDS])

    chunks = split_into_chunks(text)
    summaries = []

    for chunk in chunks:
        if not chunk.strip():
            continue
        result = query_inference_api(chunk, min_len, max_len)
        summaries.append(result)

    combined_summary = ' '.join(summaries)

    try:
        summary_enum = SummaryType[summary_type.replace(' ', '_').upper()]
    except KeyError:
        summary_enum = SummaryType.PARAGRAPH

    return summary_enum.format(combined_summary)
