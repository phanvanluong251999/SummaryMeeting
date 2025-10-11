from flask import Flask, request, jsonify, render_template, session
import os
from docx import Document
from PyPDF2 import PdfReader
import openai
import json
from transformers import pipeline
from pydub import AudioSegment
from datetime import datetime
import re

# -------- CONFIG --------
MODEL_NAME = "openai/whisper-small"  # You can change to "openai/whisper-base" or "openai/whisper-large-v3"
CHUNK_LENGTH_MS = 30 * 1000          # 30 seconds per chunk
TEMP_DIR = "audio_chunks"            # folder for temporary split files
UPLOAD_DIR = "uploads"
OUTPUT_DIR = "outputs"
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
    api_key="xxx"
)
clientGPT4 = openai.OpenAI(
    base_url="https://aiportalapi.stu-platform.live/jpe",
    api_key="xxxx"
)

app = Flask(__name__)
app.config['UPLOAD_FOLDER'] = 'uploads'

# Method read text from file TXT/DOCX/PDF
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

# API load file (text or audio)
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
    os.makedirs(OUTPUT_DIR, exist_ok=True)

    match = re.search(r"(\d{1,2}[/-]\d{1,2}[/-]\d{4})", text)
    if match:
        raw_date = match.group(1).replace("/", "-")
        parts = raw_date.split("-")
        if len(parts[0]) == 4:  # yyyy-mm-dd
            meeting_date = raw_date
        else:
            meeting_date = f"{parts[2]}-{parts[1].zfill(2)}-{parts[0].zfill(2)}"
    else:
        meeting_date = datetime.now().strftime("%Y-%m-%d")
    print("Meeting date:" + meeting_date)
    # File name
    output_file = os.path.join(OUTPUT_DIR, f"{meeting_date}_meeting_summary.txt")

    # Save meeting to file
    meeting_count = 1
    if os.path.exists(output_file):
        with open(output_file, "r", encoding="utf-8") as f:
            existing = f.read()
            meeting_count = existing.count("Meeting ") + 1

    with open(output_file, "a", encoding="utf-8") as f:
        f.write(f"\n\n=== Meeting {meeting_count} ({meeting_date}) ===\n")
        f.write(summary.strip() + "\n")

    print(f"✅ Summary saved to {output_file}")
    return jsonify({"summary": summary})

@app.route("/")
def index():
    return render_template("index.html")

app.secret_key = "supersecretkey"
@app.route("/chatbot", methods=["POST"])
def chatbot():
    data = request.json
    question = data.get("question", "").strip()
    if not question:
        return jsonify({"error": "No question provided"}), 400

    # get file and history chat from session
    current_file = session.get("current_meeting_file", None)
    chat_history = session.get("chat_history", [])

    # ----------- DEFINE TOOLS (FUNCTION CALLING) -----------
    tools = [
        {
            "type": "function",
            "function": {
                "name": "select_meeting_by_date",
                "description": "Selects the meeting file for a given date (in dd/mm/yyyy or yyyy-mm-dd format)",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "date": {
                            "type": "string",
                            "description": "The date of the meeting to select"
                        }
                    },
                    "required": ["date"]
                }
            }
        },
        {
            "type": "function",
            "function": {
                "name": "answer_meeting_question",
                "description": "Answers user questions based on the currently selected meeting summary",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "question": {"type": "string"}
                    },
                    "required": ["question"]
                }
            }
        }
    ]
    # --------------------------------------------------------

    # Create list message
    messages = [{"role": "system", "content": "You are a meeting assistant that can select and answer based on meeting summaries."}]
    messages.extend(chat_history)
    messages.append({"role": "user", "content": question})

    # Send request to GPT
    response = clientGPT4.chat.completions.create(
        model="gpt-4o",
        messages=messages,
        tools=tools,
        tool_choice="auto"
    )

    message = response.choices[0].message

    if message.tool_calls:
        call = message.tool_calls[0]
        func_name = call.function.name
        args = json.loads(call.function.arguments)

        if func_name == "select_meeting_by_date":
            user_date = args["date"].replace("/", "-")
            parts = user_date.split("-")
            if len(parts[0]) == 4:
                formatted_date = user_date
            else:
                formatted_date = f"{parts[2]}-{parts[1].zfill(2)}-{parts[0].zfill(2)}"

            file_name = f"{formatted_date}_meeting_summary.txt"
            file_path = os.path.join(OUTPUT_DIR, file_name)

            if os.path.exists(file_path):
                session["current_meeting_file"] = file_name
                answer = f"✅ Đã chọn cuộc họp ngày {formatted_date}. Bạn có thể hỏi tiếp về ngày này."
            else:
                answer = f"⚠️ Không tìm thấy cuộc họp nào vào ngày {formatted_date}."

            # Save to history
            chat_history.append({"role": "user", "content": question})
            chat_history.append({"role": "assistant", "content": answer})
            session["chat_history"] = chat_history
            return jsonify({"answer": answer})

        elif func_name == "answer_meeting_question":
            q = args["question"]
            summaries = ""

            if current_file and os.path.exists(os.path.join(OUTPUT_DIR, current_file)):
                with open(os.path.join(OUTPUT_DIR, current_file), "r", encoding="utf-8") as f:
                    summaries = f.read()
            else:
                for file in os.listdir(OUTPUT_DIR):
                    if file.endswith(".txt"):
                        with open(os.path.join(OUTPUT_DIR, file), "r", encoding="utf-8") as f:
                            summaries += f"\n\n--- {file} ---\n" + f.read()

            if not summaries.strip():
                answer = "❗ Chưa có dữ liệu cuộc họp nào để tham chiếu."
            else:
                sub_prompt = f"""
                You are a meeting assistant. Answer the question based on the following meeting summaries.
                If the answer is not found, reply in Vietnamese: 'Tôi không tìm thấy thông tin đó trong các cuộc họp.'

                Meeting summaries:
                {summaries}

                User question: {q}
                """

                sub_response = clientGPT4.chat.completions.create(
                    model="gpt-4o",
                    messages=[
                        {"role": "system", "content": "You are a helpful assistant answering meeting questions."},
                        {"role": "user", "content": sub_prompt}
                    ]
                )

                answer = sub_response.choices[0].message.content.strip()

            # Save to history
            chat_history.append({"role": "user", "content": question})
            chat_history.append({"role": "assistant", "content": answer})
            session["chat_history"] = chat_history

            return jsonify({"answer": answer})
    else:
        answer = message.content or "Tôi chưa rõ câu hỏi của bạn."
        chat_history.append({"role": "user", "content": question})
        chat_history.append({"role": "assistant", "content": answer})
        session["chat_history"] = chat_history
        return jsonify({"answer": answer})

if __name__ == "__main__":
    os.makedirs("uploads", exist_ok=True)
    app.run(debug=True)


