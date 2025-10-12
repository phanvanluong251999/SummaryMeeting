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
import logging
from typing import Optional, List, Tuple
from werkzeug.utils import secure_filename
from functools import lru_cache
import shutil

# -------- CONFIGURATION --------
class Config:
    """Application configuration"""
    MODEL_NAME = "openai/whisper-small"
    CHUNK_LENGTH_MS = 30 * 1000  # 30 seconds
    TEMP_DIR = "audio_chunks"
    UPLOAD_DIR = "uploads"
    OUTPUT_DIR = "output"  # Folder for saving summaries
    MAX_FILE_SIZE = 100 * 1024 * 1024  # 100MB
    ALLOWED_TEXT_EXTENSIONS = {'.txt', '.docx', '.pdf'}
    ALLOWED_AUDIO_EXTENSIONS = {'.mp3', '.wav', '.m4a'}
    SECRET_KEY = os.environ.get('SECRET_KEY', 'supersecretkey')
    
    # API Configuration
    OPENAI_BASE_URL = os.environ.get('OPENAI_BASE_URL', 'https://aiportalapi.stu-platform.live/jpe')
    OPENAI_API_KEY = os.environ.get('OPENAI_API_KEY', 'sk-9CcbggVJxVgap1rjNkUvtQ')

# -------- LOGGING SETUP --------
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# -------- FLASK APP INITIALIZATION --------
app = Flask(__name__)
app.config['UPLOAD_FOLDER'] = Config.UPLOAD_DIR
app.config['MAX_CONTENT_LENGTH'] = Config.MAX_FILE_SIZE
app.secret_key = Config.SECRET_KEY

# -------- OPENAI CLIENT INITIALIZATION --------
try:
    client = openai.OpenAI(
        base_url=Config.OPENAI_BASE_URL,
        api_key=Config.OPENAI_API_KEY
    )
    logger.info("OpenAI client initialized successfully")
except Exception as e:
    logger.error(f"Failed to initialize OpenAI client: {e}")
    client = None

# -------- UTILITY FUNCTIONS --------
def ensure_directories():
    """Ensure all required directories exist"""
    for directory in [Config.UPLOAD_DIR, Config.OUTPUT_DIR, Config.TEMP_DIR]:
        os.makedirs(directory, exist_ok=True)

def cleanup_temp_files(file_list: List[str], remove_dir: bool = True):
    """Clean up temporary files and optionally the directory"""
    for file_path in file_list:
        try:
            if os.path.exists(file_path):
                os.remove(file_path)
        except Exception as e:
            logger.warning(f"Failed to remove temp file {file_path}: {e}")
    
    if remove_dir and os.path.exists(Config.TEMP_DIR):
        try:
            shutil.rmtree(Config.TEMP_DIR)
        except Exception as e:
            logger.warning(f"Failed to remove temp directory: {e}")

def validate_file_extension(filename: str, allowed_extensions: set) -> bool:
    """Validate file extension"""
    ext = os.path.splitext(filename)[1].lower()
    return ext in allowed_extensions

def parse_date_from_text(text: str) -> str:
    """Extract and format date from text"""
    match = re.search(r"(\d{1,2}[/-]\d{1,2}[/-]\d{4})", text)
    if match:
        raw_date = match.group(1).replace("/", "-")
        parts = raw_date.split("-")
        if len(parts[0]) == 4:  # yyyy-mm-dd
            return raw_date
        else:  # dd-mm-yyyy
            return f"{parts[2]}-{parts[1].zfill(2)}-{parts[0].zfill(2)}"
    return datetime.now().strftime("%Y-%m-%d")

# -------- AUDIO PROCESSING --------
def split_audio(file_path: str, chunk_length_ms: int = Config.CHUNK_LENGTH_MS) -> List[str]:
    """Split audio file into manageable chunks"""
    try:
        logger.info(f"Splitting audio file: {file_path}")
        audio = AudioSegment.from_file(file_path)
        duration_min = len(audio) / 60000
        logger.info(f"Total duration: {duration_min:.2f} minutes")

        os.makedirs(Config.TEMP_DIR, exist_ok=True)
        chunks = []

        for i in range(0, len(audio), chunk_length_ms):
            chunk = audio[i:i + chunk_length_ms]
            chunk_filename = os.path.join(Config.TEMP_DIR, f"chunk_{i//chunk_length_ms}.wav")
            chunk.export(chunk_filename, format="wav")
            chunks.append(chunk_filename)
        
        logger.info(f"Split into {len(chunks)} chunks")
        return chunks
    except Exception as e:
        logger.error(f"Error splitting audio: {e}")
        raise

def transcribe_audio(file_path: str) -> str:
    """Transcribe audio file using Whisper model"""
    chunks = []
    try:
        logger.info("Loading Whisper model...")
        pipe = pipeline(
            "automatic-speech-recognition",
            model=Config.MODEL_NAME
        )

        chunks = split_audio(file_path)
        full_text = []

        logger.info("Starting transcription...")
        for i, chunk in enumerate(chunks):
            logger.info(f"Transcribing chunk {i + 1}/{len(chunks)}")
            result = pipe(chunk)
            text = result["text"].strip()
            full_text.append(text)
        
        return " ".join(full_text)
    
    except Exception as e:
        logger.error(f"Error during transcription: {e}")
        raise
    finally:
        cleanup_temp_files(chunks, remove_dir=True)

# -------- TEXT EXTRACTION --------
def extract_text(file_path: str) -> Optional[str]:
    """Extract text from various file formats"""
    ext = os.path.splitext(file_path)[1].lower()
    
    try:
        if ext == ".txt":
            with open(file_path, "r", encoding="utf-8") as f:
                return f.read()
        
        elif ext == ".docx":
            doc = Document(file_path)
            return "\n".join(para.text for para in doc.paragraphs)
        
        elif ext == ".pdf":
            reader = PdfReader(file_path)
            texts = []
            for page in reader.pages:
                page_text = page.extract_text()
                if page_text:
                    texts.append(page_text)
            return "\n".join(texts)
        
        else:
            logger.warning(f"Unsupported file extension: {ext}")
            return None
    
    except Exception as e:
        logger.error(f"Error extracting text from {file_path}: {e}")
        return None

# -------- API ROUTES --------
@app.route("/")
def index():
    """Render main page"""
    return render_template("index.html")

@app.route("/load_file", methods=["POST"])
def load_file():
    """Handle file upload and processing"""
    try:
        file = request.files.get("meeting_file")
        if not file or file.filename == '':
            return jsonify({"error": "No file uploaded"}), 400

        filename = secure_filename(file.filename)
        ext = os.path.splitext(filename)[1].lower()
        
        # Validate file type
        all_extensions = Config.ALLOWED_TEXT_EXTENSIONS | Config.ALLOWED_AUDIO_EXTENSIONS
        if not validate_file_extension(filename, all_extensions):
            return jsonify({"error": "Unsupported file format"}), 400

        # Save file
        ensure_directories()
        file_path = os.path.join(app.config['UPLOAD_FOLDER'], filename)
        file.save(file_path)
        
        logger.info(f"File uploaded: {filename}")

        # Process based on file type
        text = None
        if ext in Config.ALLOWED_TEXT_EXTENSIONS:
            logger.info(f"Processing text file: {filename}")
            text = extract_text(file_path)
            if not text:
                return jsonify({"error": "Unable to extract text from file"}), 400
        
        elif ext in Config.ALLOWED_AUDIO_EXTENSIONS:
            logger.info(f"Processing audio file: {filename}")
            try:
                text = transcribe_audio(file_path)
                if not text:
                    return jsonify({"error": "Unable to transcribe audio"}), 400
            except Exception as e:
                logger.error(f"Audio transcription error: {e}")
                return jsonify({"error": f"Audio transcription failed: {str(e)}"}), 500
        
        else:
            return jsonify({"error": "File format not supported"}), 400

        logger.info(f"File processed successfully. Text length: {len(text)} characters")
        return jsonify({
            "success": True,
            "filename": filename,
            "text": text,
            "length": len(text)
        })
    
    except Exception as e:
        logger.error(f"Error in load_file: {e}", exc_info=True)
        return jsonify({"error": f"Failed to process file: {str(e)}"}), 500

def generate_meeting_title(text: str, max_length: int = 50) -> str:
    """Generate a descriptive title for the meeting using AI"""
    try:
        if not client:
            return "Meeting"
        
        prompt = f"""
        Based on this meeting transcript, generate a SHORT, descriptive title (maximum 5 words).
        The title should capture the main topic or purpose.
        Return ONLY the title, nothing else. No quotes, no explanations.
        Use title case (capitalize first letter of each word).
        
        Examples of good titles:
        - "Q1 Sales Review"
        - "Product Launch Planning"
        - "Team Budget Discussion"
        
        Transcript excerpt:
        {text[:1000]}
        """
        
        response = client.chat.completions.create(
            model="gpt-4o-mini",
            messages=[
                {"role": "system", "content": "You are a helpful assistant that creates concise meeting titles."},
                {"role": "user", "content": prompt}
            ],
            temperature=0.3,
            max_tokens=50
        )
        
        title = response.choices[0].message.content.strip()
        title = title.replace('"', '').replace("'", "").strip()
        title = re.sub(r'[<>:"/\\|?*]', '', title)
        
        if len(title) > max_length:
            title = title[:max_length].rsplit(' ', 1)[0]
        
        return title if title else "Meeting"
    
    except Exception as e:
        logger.error(f"Error generating title: {e}")
        return "Meeting"

def sanitize_filename(filename: str) -> str:
    """Sanitize filename to be filesystem-safe"""
    filename = filename.replace(' ', '_')
    filename = re.sub(r'[<>:"/\\|?*]', '', filename)
    return filename

def get_unique_filename(base_path: str, extension: str = ".txt") -> str:
    """Generate unique filename if file already exists"""
    if not os.path.exists(base_path + extension):
        return base_path + extension
    
    counter = 1
    while os.path.exists(f"{base_path}_{counter}{extension}"):
        counter += 1
    
    return f"{base_path}_{counter}{extension}"

@app.route("/summarize", methods=["POST"])
def summarize():
    """Generate meeting summary using AI (without saving)"""
    try:
        logger.info("=" * 80)
        logger.info("SUMMARIZE ENDPOINT CALLED")
        logger.info("=" * 80)
        
        if not client:
            logger.error("OpenAI client not available")
            return jsonify({"error": "AI service not available"}), 503

        data = request.json
        logger.info(f"Request data keys: {data.keys() if data else 'No data'}")
        
        text = data.get("text", "") if data else ""
        logger.info(f"Text length received: {len(text)} characters")
        
        if not text:
            logger.error("No text provided in request")
            return jsonify({"error": "No text provided"}), 400

        if len(text) < 10:
            logger.error(f"Text too short: {len(text)} characters")
            return jsonify({"error": "Text too short to summarize"}), 400

        logger.info(f"Text preview (first 200 chars): {text[:200]}")
        logger.info("Generating meeting summary...")

        # Generate meeting summary
        prompt = f"""
        Summarize the following meeting transcript with key points, decisions, and action items. 
        Please ensure the summary is written in the same language as the transcript. 
        
        Format your response as follows:
        1. Brief Overview (2-3 sentences)
        2. Key Discussion Points (bullet points)
        3. Decisions Made (bullet points)
        4. Action Items (bullet points with responsible parties if mentioned)
        
        Transcript:
        {text}
        """

        logger.info("Calling OpenAI API...")
        response = client.chat.completions.create(
            model="gpt-4o-mini",
            messages=[
                {"role": "system", "content": "You are a helpful assistant specialized in summarizing meeting notes."},
                {"role": "user", "content": prompt}
            ],
            temperature=0
        )
        
        summary = response.choices[0].message.content.strip()
        logger.info(f"Summary generated successfully. Length: {len(summary)} characters")
        logger.info(f"Summary preview: {summary[:200]}")
        
        # Generate meeting title
        logger.info("Generating meeting title...")
        meeting_title = generate_meeting_title(text)
        logger.info(f"Generated title: {meeting_title}")
        
        # Extract or use current date
        meeting_date = parse_date_from_text(text)
        logger.info(f"Meeting date: {meeting_date}")
        
        # Store in session for later saving
        session["pending_summary"] = {
            "summary": summary,
            "title": meeting_title,
            "date": meeting_date,
            "original_text": text
        }
        logger.info("Summary stored in session")
        
        response_data = {
            "success": True,
            "summary": summary,
            "title": meeting_title,
            "date": meeting_date
        }
        
        logger.info("Sending successful response")
        logger.info("=" * 80)
        return jsonify(response_data)
    
    except Exception as e:
        logger.error("=" * 80)
        logger.error(f"ERROR in summarize endpoint: {e}")
        logger.error(f"Error type: {type(e).__name__}")
        logger.error(f"Error details: {str(e)}")
        logger.error("=" * 80, exc_info=True)
        return jsonify({"error": f"Failed to generate summary: {str(e)}"}), 500

@app.route("/save_summary", methods=["POST"])
def save_summary():
    """Save the edited summary to input folder with format: {datetime}_{title}.txt"""
    try:
        data = request.json
        summary = data.get("summary", "")
        title = data.get("title", "")
        date = data.get("date", "")
        
        # Get from session if not provided
        pending = session.get("pending_summary", {})
        if not summary and pending:
            summary = pending.get("summary", "")
        if not title and pending:
            title = pending.get("title", "Meeting")
        if not date and pending:
            date = pending.get("date", datetime.now().strftime("%Y-%m-%d"))
        
        # Allow user to edit title
        if data.get("title"):
            title = data.get("title")
        
        if not summary:
            return jsonify({"error": "No summary to save"}), 400
        
        # Create filename with format: YYYYMMDD_HHMMSS_{title}.txt
        current_datetime = datetime.now().strftime("%Y%m%d_%H%M%S")
        safe_title = sanitize_filename(title)
        filename = f"{current_datetime}_{safe_title}.txt"
        
        # Ensure unique filename
        ensure_directories()
        output_file = os.path.join(Config.OUTPUT_DIR, filename)
        
        # If file exists, add counter
        counter = 1
        while os.path.exists(output_file):
            filename = f"{current_datetime}_{safe_title}_{counter}.txt"
            output_file = os.path.join(Config.OUTPUT_DIR, filename)
            counter += 1
        
        # Create meeting record with metadata
        meeting_record = f"""{'='*80}
MEETING SUMMARY
{'='*80}
Title: {title}
Date: {date}
Generated: {datetime.now().strftime("%Y-%m-%d %H:%M:%S")}
File: {filename}
{'='*80}

{summary.strip()}

{'='*80}
"""
        
        # Save to input folder
        with open(output_file, "w", encoding="utf-8") as f:
            f.write(meeting_record)

        logger.info(f"Summary saved to {output_file}")
        
        # Clear pending summary from session
        session.pop("pending_summary", None)
        
        return jsonify({
            "success": True,
            "message": "Summary saved successfully to output folder",
            "filename": filename,
            "filepath": output_file,
            "title": title,
            "date": date
        })
    
    except Exception as e:
        logger.error(f"Error in save_summary: {e}", exc_info=True)
        return jsonify({"error": f"Failed to save summary: {str(e)}"}), 500

def load_meeting_from_file(filepath: str) -> Optional[dict]:
    """Load meeting data from a file"""
    try:
        with open(filepath, "r", encoding="utf-8") as f:
            content = f.read()
            
        # Parse metadata
        title_match = re.search(r"Title:\s*(.+)", content)
        date_match = re.search(r"Date:\s*(.+)", content)
        file_match = re.search(r"File:\s*(.+)", content)
        
        # Extract summary (content after second separator)
        parts = content.split("="*80)
        summary = parts[2].strip() if len(parts) > 2 else ""
        
        return {
            "title": title_match.group(1).strip() if title_match else "Unknown",
            "date": date_match.group(1).strip() if date_match else "",
            "filename": file_match.group(1).strip() if file_match else os.path.basename(filepath),
            "summary": summary,
            "filepath": filepath
        }
    except Exception as e:
        logger.error(f"Error loading meeting from {filepath}: {e}")
        return None

def get_all_meetings() -> List[dict]:
    """Get all meetings from output folder"""
    meetings = []
    ensure_directories()
    
    if os.path.exists(Config.OUTPUT_DIR):
        for filename in os.listdir(Config.OUTPUT_DIR):
            if filename.endswith(".txt"):
                filepath = os.path.join(Config.OUTPUT_DIR, filename)
                meeting_data = load_meeting_from_file(filepath)
                if meeting_data:
                    meetings.append(meeting_data)
    
    # Sort by filename (datetime is in filename)
    meetings.sort(key=lambda x: x["filename"], reverse=True)
    return meetings

@app.route("/chatbot", methods=["POST"])
def chatbot():
    """Handle chatbot interactions with meeting context"""
    try:
        if not client:
            return jsonify({"error": "AI service not available"}), 503

        data = request.json
        question = data.get("question", "").strip()
        
        if not question:
            return jsonify({"error": "No question provided"}), 400

        # Load all meetings from input folder
        all_meetings = get_all_meetings()
        
        # Create context from all meetings
        context = "Available meetings:\n\n"
        for meeting in all_meetings[:10]:  # Limit to last 10 meetings
            context += f"Title: {meeting['title']}\n"
            context += f"Date: {meeting['date']}\n"
            context += f"Summary: {meeting['summary'][:300]}...\n\n"
        
        # Get chat history
        chat_history = session.get("chat_history", [])
        
        # Build messages
        messages = [
            {"role": "system", "content": f"""You are a helpful meeting assistant. 
You have access to meeting summaries from the output folder. 
Use this information to answer user questions about meetings.

{context}

When answering:
- Be specific and cite which meeting you're referring to
- If information is not available, say so politely
- Suggest related information if available
- Answer in the same language as the question"""}
        ]
        
        # Add chat history
        messages.extend(chat_history[-10:])
        messages.append({"role": "user", "content": question})

        # Get AI response
        response = client.chat.completions.create(
            model="gpt-4o-mini",
            messages=messages,
            temperature=0.3
        )

        answer = response.choices[0].message.content or "I'm not sure how to answer that."

        # Update chat history
        chat_history.append({"role": "user", "content": question})
        chat_history.append({"role": "assistant", "content": answer})
        session["chat_history"] = chat_history[-20:]

        return jsonify({"answer": answer})
    
    except Exception as e:
        logger.error(f"Error in chatbot: {e}")
        return jsonify({"error": "Failed to process question"}), 500

@app.route("/list_meetings", methods=["GET"])
def list_meetings():
    """List all available meeting summaries from output folder"""
    try:
        meetings = get_all_meetings()
        
        # Group by date
        grouped_meetings = {}
        for meeting in meetings:
            date = meeting["date"]
            if date not in grouped_meetings:
                grouped_meetings[date] = []
            grouped_meetings[date].append(meeting)
        
        return jsonify({
            "meetings": meetings,
            "grouped": grouped_meetings,
            "total": len(meetings)
        })
    
    except Exception as e:
        logger.error(f"Error listing meetings: {e}")
        return jsonify({"error": "Failed to list meetings"}), 500

# -------- ERROR HANDLERS --------
@app.errorhandler(413)
def request_entity_too_large(error):
    return jsonify({"error": "File too large. Maximum size is 100MB."}), 413

@app.errorhandler(500)
def internal_server_error(error):
    logger.error(f"Internal server error: {error}")
    return jsonify({"error": "Internal server error"}), 500

# -------- MAIN --------
if __name__ == "__main__":
    ensure_directories()
    logger.info(f"Summaries will be saved to: {os.path.abspath(Config.OUTPUT_DIR)}")
    app.run(debug=True, host='0.0.0.0', port=5000)