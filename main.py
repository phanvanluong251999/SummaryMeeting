from flask import Flask, request, jsonify, render_template
import os
from docx import Document
from PyPDF2 import PdfReader
import openai

from transformers import pipeline
from pydub import AudioSegment

# -------- CONFIG --------
MODEL_NAME = "openai/whisper-small"  # You can change to "openai/whisper-base" or "openai/whisper-large-v3"
CHUNK_LENGTH_MS = 30 * 1000          # 30 seconds per chunk
TEMP_DIR = "audio_chunks"            # folder for temporary split files
# -------------------------

def split_audio(file_path, chunk_length_ms=CHUNK_LENGTH_MS):
    """Split audio into chunks of given length (default 30 seconds)."""
    print(f"🔹 Splitting audio file: {file_path}")
    audio = AudioSegment.from_file(file_path)
    duration_min = len(audio) / 60000
    print(f"   Total duration: {duration_min:.2f} minutes")

    os.makedirs(TEMP_DIR, exist_ok=True)
    chunks = []

    for i in range(0, len(audio), chunk_length_ms):
        chunk = audio[i:i + chunk_length_ms]
        chunk_filename = os.path.join(TEMP_DIR, f"chunk_{i//chunk_length_ms}.wav")
        chunk.export(chunk_filename, format="wav")
        chunks.append(chunk_filename)
    print(f"   Split into {len(chunks)} chunks.")
    return chunks

def transcribe_audio(file_path):
    """Transcribe long audio files by splitting them automatically."""
    print("🔹 Loading Whisper model...")
    pipe = pipeline(
        "automatic-speech-recognition",
        model=MODEL_NAME
    )

    chunks = split_audio(file_path)
    full_text = ""

    print("🔹 Starting transcription...")
    for i, chunk in enumerate(chunks):
        print(f"   -> Transcribing chunk {i + 1}/{len(chunks)} ...")
        result = pipe(chunk)
        text = result["text"].strip()
        print(text)
        full_text += text + " "
    
    # Cleanup temporary files
    for c in chunks:
        os.remove(c)
    os.rmdir(TEMP_DIR)

    print("\n✅ Transcription complete!")
    return full_text.strip()

client = openai.OpenAI(
    base_url="https://aiportalapi.stu-platform.live/jpe",
    api_key="xxxx"
)
clientGPT4 = openai.OpenAI(
    base_url="https://aiportalapi.stu-platform.live/jpe",
    api_key="xxxxx"
)

app = Flask(__name__)
app.config['UPLOAD_FOLDER'] = 'uploads'

# Hàm đọc text từ file TXT/DOCX/PDF
def extract_text(file_path):
    ext = os.path.splitext(file_path)[1].lower()
    text = ""
    if ext == ".txt":
        with open(file_path, "r", encoding="utf-8") as f:
            text = f.read()
    elif ext == ".docx":
        doc = Document(file_path)
        for para in doc.paragraphs:
            text += para.text + "\n"
    elif ext == ".pdf":
        reader = PdfReader(file_path)
        for page in reader.pages:
            page_text = page.extract_text()
            if page_text:
                text += page_text + "\n"
    else:
        text = None
    return text

# API load file (text hoặc audio)
@app.route("/load_file", methods=["POST"])
def load_file():
    file = request.files.get("meeting_file")
    if not file:
        return jsonify({"error": "No file uploaded"}), 400

    filename = file.filename
    os.makedirs(app.config['UPLOAD_FOLDER'], exist_ok=True)
    file_path = os.path.join(app.config['UPLOAD_FOLDER'], filename)
    file.save(file_path)

    ext = os.path.splitext(filename)[1].lower()
    if ext in [".txt", ".docx", ".pdf"]:
        text = extract_text(file_path)
        if not text:
            text = "Không thể đọc file này."
    elif ext in [".mp3", ".wav", ".m4a"]:
        with open(file_path, "rb") as f:
           result =  transcribe_audio(f)
            
        text = result
    else:
        text = "Định dạng file không được hỗ trợ."

    return jsonify({"filename": filename, "text": text})

# API tóm tắt
@app.route("/summarize", methods=["POST"])
def summarize():
    data = request.json
    text = data.get("text", "")
    if not text:
        return jsonify({"error": "No text provided"}), 400

    prompt = f"""
    Summarize the following meeting transcript with key points, decisions, and action items. 
    Please ensure the summary is written in the same language as the transcript. 
    Transcript:
    {text}
    """
    response = clientGPT4.chat.completions.create(
        model="gpt-4o",
        messages=[
            {"role": "system", "content": "You are a helpful assistant specialized in summarizing meeting notes."},
            {"role": "user", "content": prompt}
            ],
        temperature=0
    )
    summary = response.choices[0].message.content.strip()
    return jsonify({"summary": summary})

@app.route("/")
def index():
    return render_template("index.html")

if __name__ == "__main__":
    os.makedirs("uploads", exist_ok=True)
    app.run(debug=True)
