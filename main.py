from flask import Flask, request, jsonify, render_template, session, Response, stream_with_context
import os
from dotenv import load_dotenv
from docx import Document

# Load environment variables from .env file
load_dotenv()
from PyPDF2 import PdfReader
import openai
import json
from datetime import datetime
import re
import logging
from typing import Optional, List, Tuple, Dict
from werkzeug.utils import secure_filename
import chromadb
from chromadb.utils import embedding_functions
import time
import threading
import queue

# -------- CONFIGURATION --------
class Config:
    """Application configuration"""
    UPLOAD_DIR = "uploads"
    OUTPUT_DIR = "outputs"
    CHROMA_DIR = "chroma_db"  # ChromaDB storage directory
    MAX_FILE_SIZE = 100 * 1024 * 1024  # 100MB
    ALLOWED_TEXT_EXTENSIONS = {'.txt', '.docx', '.pdf'}
    ALLOWED_AUDIO_EXTENSIONS = {'.mp3', '.wav', '.m4a'}
    SECRET_KEY = os.environ.get('SECRET_KEY', 'supersecretkey')

    # OpenAI Configuration (for summarization only, not transcription)
    OPENAI_BASE_URL = os.environ.get('OPENAI_BASE_URL', 'https://aiportalapi.stu-platform.live/jpe')
    OPENAI_API_KEY = os.environ.get('OPENAI_API_KEY', 'sk-9CcbggVJxVgap1rjNkUvtQ')

    # AssemblyAI Configuration (for audio transcription)
    ASSEMBLYAI_API_KEY = os.environ.get('ASSEMBLYAI_API_KEY', '')

    # AssemblyAI Transcription Options
    ENABLE_SPEAKER_LABELS = os.environ.get('ENABLE_SPEAKER_LABELS', 'false').lower() == 'true'
    LANGUAGE_CODE = os.environ.get('LANGUAGE_CODE', 'en')  # Language code or None for auto-detect

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

# -------- PROGRESS TRACKING --------
# Store progress updates for streaming to clients
progress_queues = {}

def create_progress_queue(task_id: str) -> queue.Queue:
    """Create a new progress queue for a task"""
    q = queue.Queue()
    progress_queues[task_id] = q
    return q

def send_progress(task_id: str, message: str, partial_text: str = None, is_complete: bool = False):
    """Send a progress update to the queue"""
    if task_id in progress_queues:
        update = {
            "message": message,
            "timestamp": datetime.now().isoformat(),
            "is_complete": is_complete
        }
        if partial_text is not None:
            update["partial_text"] = partial_text
        progress_queues[task_id].put(update)
        logger.info(f"[{task_id}] {message}")

def cleanup_progress_queue(task_id: str):
    """Clean up a progress queue"""
    if task_id in progress_queues:
        del progress_queues[task_id]

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

# -------- ASSEMBLYAI CLIENT INITIALIZATION --------
try:
    import assemblyai as aai
    if Config.ASSEMBLYAI_API_KEY:
        aai.settings.api_key = Config.ASSEMBLYAI_API_KEY
        logger.info("✅ AssemblyAI client initialized successfully")
        logger.info(f"   API Key: {Config.ASSEMBLYAI_API_KEY[:10]}...")
        assemblyai_client = aai
    else:
        logger.warning("⚠️ AssemblyAI API key not provided")
        assemblyai_client = None
except Exception as e:
    logger.error(f"❌ Failed to initialize AssemblyAI client: {e}")
    assemblyai_client = None

# -------- CHROMADB INITIALIZATION --------
try:
    chroma_client = chromadb.PersistentClient(path=Config.CHROMA_DIR)

    # Dùng text-embedding-3-small để tăng độ chính xác tìm kiếm
    openai_ef = embedding_functions.OpenAIEmbeddingFunction(
        api_base="https://aiportalapi.stu-platform.live/jpe",
        api_key="sk-GRpLsKVWmd1jVxaI7yssZA",
        model_name="text-embedding-3-small"
    )

    meeting_collection = chroma_client.get_or_create_collection(
        name="meeting_summaries",
        embedding_function=openai_ef,
        metadata={"description": "Collection of meeting summaries with semantic search"}
    )

    logger.info(f"✅ ChromaDB initialized with text-embedding-3-small. Current count: {meeting_collection.count()}")
except Exception as e:
    logger.error(f"Failed to initialize ChromaDB: {e}")
    import traceback
    logger.error(traceback.format_exc())
    chroma_client = None
    meeting_collection = None

# -------- CHROMADB HELPER FUNCTIONS --------
def save_summary_to_chromadb(
    summary: str,
    title: str,
    date: str,
    original_text: str,
    filename: str
) -> bool:
    """Save meeting summary to ChromaDB for semantic search"""
    try:
        if not meeting_collection:
            logger.warning("ChromaDB collection not available")
            return False
        
        # Create unique ID based on date and filename
        doc_id = f"{date}_{filename.replace('.txt', '')}"
        
        logger.info(f"Attempting to save to ChromaDB with ID: {doc_id}")
        
        # Prepare metadata
        metadata = {
            "title": title,
            "date": date,
            "filename": filename,
            "created_at": datetime.now().isoformat(),
            "text_length": len(original_text)
        }
        
        logger.info(f"Metadata: {metadata}")
        
        # Add document to collection
        # ChromaDB will automatically generate embeddings
        meeting_collection.add(
            documents=[summary],
            metadatas=[metadata],
            ids=[doc_id]
        )
        
        # Verify it was added
        new_count = meeting_collection.count()
        logger.info(f"✅ Successfully saved to ChromaDB. New count: {new_count}")
        return True
        
    except Exception as e:
        logger.error(f"Error saving to ChromaDB: {e}")
        import traceback
        logger.error(traceback.format_exc())
        return False

def search_meetings_chromadb(
    query: str,
    n_results: int = 5,
    date_filter: Optional[str] = None
) -> List[Dict]:
    """Search meetings using semantic similarity"""
    try:
        if not meeting_collection:
            logger.warning("ChromaDB collection not available")
            return []
        
        # Prepare where filter for date if provided
        where_filter = None
        if date_filter:
            where_filter = {"date": date_filter}
        
        # Perform semantic search
        results = meeting_collection.query(
            query_texts=[query],
            n_results=n_results,
            where=where_filter
        )
        
        # Format results
        formatted_results = []
        if results and results['documents']:
            for i in range(len(results['documents'][0])):
                formatted_results.append({
                    'id': results['ids'][0][i],
                    'summary': results['documents'][0][i],
                    'metadata': results['metadatas'][0][i],
                    'distance': results['distances'][0][i] if 'distances' in results else None
                })
        
        logger.info(f"ChromaDB search found {len(formatted_results)} results")
        return formatted_results
        
    except Exception as e:
        logger.error(f"Error searching ChromaDB: {e}")
        return []

def get_meeting_by_date_chromadb(date: str) -> List[Dict]:
    """Get all meetings for a specific date from ChromaDB"""
    try:
        if not meeting_collection:
            return []
        
        results = meeting_collection.get(
            where={"date": date}
        )
        
        formatted_results = []
        if results and results['documents']:
            for i in range(len(results['documents'])):
                formatted_results.append({
                    'id': results['ids'][i],
                    'summary': results['documents'][i],
                    'metadata': results['metadatas'][i]
                })
        
        return formatted_results
        
    except Exception as e:
        logger.error(f"Error getting meetings by date: {e}")
        return []

def get_all_meeting_dates_chromadb() -> List[str]:
    """Get all unique meeting dates from ChromaDB"""
    try:
        if not meeting_collection:
            return []
        
        # Get all documents
        results = meeting_collection.get()
        
        # Extract unique dates
        dates = set()
        if results and results['metadatas']:
            for metadata in results['metadatas']:
                if 'date' in metadata:
                    dates.add(metadata['date'])
        
        return sorted(list(dates), reverse=True)
        
    except Exception as e:
        logger.error(f"Error getting meeting dates: {e}")
        return []

# -------- UTILITY FUNCTIONS --------
def ensure_directories():
    """Ensure all required directories exist"""
    for directory in [Config.UPLOAD_DIR, Config.OUTPUT_DIR, Config.CHROMA_DIR]:
        os.makedirs(directory, exist_ok=True)


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

# -------- AUDIO TRANSCRIPTION --------
def transcribe_audio_assemblyai(file_path: str, task_id: Optional[str] = None) -> str:
    """Transcribe audio file using AssemblyAI API with real-time text streaming"""
    start_time = time.time()
    try:
        if not assemblyai_client:
            raise Exception("AssemblyAI client not initialized")

        logger.info("🚀 Using AssemblyAI for transcription...")
        if task_id:
            send_progress(task_id, "Đang tải file âm thanh lên...")

        # Configure transcription options
        config = assemblyai_client.TranscriptionConfig(
            speaker_labels=Config.ENABLE_SPEAKER_LABELS,
            language_code=Config.LANGUAGE_CODE if Config.LANGUAGE_CODE else None
        )

        # Create transcriber
        transcriber = assemblyai_client.Transcriber(config=config)

        # Upload and transcribe
        logger.info(f"Uploading and transcribing: {file_path}")

        if task_id:
            send_progress(task_id, "Đang chuyển đổi giọng nói thành văn bản...")

        transcript = transcriber.transcribe(file_path)

        if task_id:
            send_progress(task_id, "Đã nhận kết quả, đang hiển thị...")

        # Check if transcription was successful
        if transcript.status == assemblyai_client.TranscriptStatus.error:
            raise Exception(f"AssemblyAI transcription failed: {transcript.error}")

        # Format output based on whether speaker labels are enabled
        if Config.ENABLE_SPEAKER_LABELS and transcript.utterances:
            logger.info("✅ Transcription with speaker labels completed")
            formatted_text = []
            for utterance in transcript.utterances:
                speaker = f"Speaker {utterance.speaker}"
                text = utterance.text
                formatted_text.append(f"{speaker}: {text}")
            result = "\n".join(formatted_text)
        else:
            logger.info("✅ Transcription completed")
            result = transcript.text

        elapsed_time = time.time() - start_time
        logger.info(f"✅ Transcription completed in {elapsed_time:.2f} seconds")
        logger.info(f"   Length: {len(result)} characters")

        # Stream the text word-by-word for real-time effect
        if task_id and result:
            # Split text into individual words
            words = result.split()
            total_words = len(words)

            # Stream word by word with FIXED speed
            accumulated_text = ""

            for i, word in enumerate(words):
                accumulated_text += (" " if accumulated_text else "") + word

                # Show progress every word for visibility
                current_word = i + 1
                send_progress(
                    task_id,
                    f"Đang hiển thị... ({current_word}/{total_words} từ)",
                    partial_text=accumulated_text
                )

                # FIXED delay - same speed for all text lengths
                time.sleep(0.05)  # 50ms per word - consistent and visible

            # Send final complete text with completion message
            send_progress(
                task_id,
                f"Hoàn thành! ({elapsed_time:.1f}s)",
                partial_text=result,
                is_complete=True
            )
        elif task_id:
            send_progress(task_id, f"Hoàn thành! ({elapsed_time:.1f}s)", is_complete=True)

        return result

    except Exception as e:
        elapsed_time = time.time() - start_time
        logger.error(f"❌ Error during AssemblyAI transcription after {elapsed_time:.2f}s: {e}")
        if task_id:
            send_progress(task_id, f"Lỗi: {str(e)}")
        raise

def transcribe_audio(file_path: str, task_id: Optional[str] = None) -> str:
    """Transcribe audio file using AssemblyAI"""
    logger.info("="*80)
    logger.info(f"🎤 TRANSCRIPTION STARTED")
    logger.info(f"   File: {os.path.basename(file_path)}")
    logger.info(f"   Provider: AssemblyAI")
    logger.info(f"   AssemblyAI Available: {assemblyai_client is not None}")
    logger.info("="*80)

    if not assemblyai_client:
        raise Exception("AssemblyAI client not initialized. Please check your ASSEMBLYAI_API_KEY in .env file")

    return transcribe_audio_assemblyai(file_path, task_id)

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

@app.route("/progress/<task_id>")
def progress_stream(task_id):
    """Server-Sent Events endpoint for streaming progress updates"""
    def generate():
        if task_id not in progress_queues:
            yield f"data: {json.dumps({'error': 'Task not found'})}\n\n"
            return

        q = progress_queues[task_id]
        while True:
            try:
                # Wait for progress update with timeout
                update = q.get(timeout=30)
                yield f"data: {json.dumps(update)}\n\n"

                # If task is complete, close stream
                if update.get('is_complete', False):
                    break
            except queue.Empty:
                # Send keep-alive
                yield f": keepalive\n\n"
            except Exception as e:
                logger.error(f"Error in progress stream: {e}")
                break

        # Clean up
        cleanup_progress_queue(task_id)

    return Response(
        stream_with_context(generate()),
        mimetype='text/event-stream',
        headers={
            'Cache-Control': 'no-cache',
            'X-Accel-Buffering': 'no'
        }
    )

@app.route("/load_file", methods=["POST"])
def load_file():
    """Handle file upload and processing with streaming progress"""
    try:
        file = request.files.get("meeting_file")
        use_streaming = request.form.get("stream") == "true"

        if not file or file.filename == '':
            return jsonify({"error": "No file uploaded"}), 400

        filename = secure_filename(file.filename)
        ext = os.path.splitext(filename)[1].lower()

        all_extensions = Config.ALLOWED_TEXT_EXTENSIONS | Config.ALLOWED_AUDIO_EXTENSIONS
        if not validate_file_extension(filename, all_extensions):
            return jsonify({"error": "Unsupported file format"}), 400

        ensure_directories()
        file_path = os.path.join(app.config['UPLOAD_FOLDER'], filename)
        file.save(file_path)

        logger.info(f"File uploaded: {filename} (streaming: {use_streaming})")

        # For text files, process immediately
        if ext in Config.ALLOWED_TEXT_EXTENSIONS:
            logger.info(f"Processing text file: {filename}")
            text = extract_text(file_path)
            if not text:
                return jsonify({"error": "Unable to extract text from file"}), 400

            return jsonify({
                "success": True,
                "filename": filename,
                "text": text,
                "length": len(text)
            })

        # For audio files with streaming
        elif ext in Config.ALLOWED_AUDIO_EXTENSIONS:
            if use_streaming:
                # Create task ID and start background processing
                task_id = f"{int(time.time())}_{filename}"
                create_progress_queue(task_id)

                def process_audio():
                    try:
                        send_progress(task_id, "Starting audio transcription...", 1)
                        text = transcribe_audio(file_path, task_id)

                        # Store result for retrieval
                        task_results[task_id] = {
                            "success": True,
                            "filename": filename,
                            "text": text,
                            "length": len(text)
                        }
                    except Exception as e:
                        logger.error(f"Background transcription error: {e}")
                        task_results[task_id] = {
                            "success": False,
                            "error": str(e)
                        }
                        send_progress(task_id, f"Error: {str(e)}", 0)

                thread = threading.Thread(target=process_audio)
                thread.daemon = True
                thread.start()

                return jsonify({
                    "success": True,
                    "task_id": task_id,
                    "streaming": True,
                    "message": "Processing started. Use /progress/{task_id} to track progress."
                })
            else:
                # Process synchronously (old behavior)
                logger.info(f"Processing audio file: {filename}")
                try:
                    text = transcribe_audio(file_path)
                    if not text:
                        return jsonify({"error": "Unable to transcribe audio"}), 400

                    return jsonify({
                        "success": True,
                        "filename": filename,
                        "text": text,
                        "length": len(text)
                    })
                except Exception as e:
                    logger.error(f"Audio transcription error: {e}")
                    return jsonify({"error": f"Audio transcription failed: {str(e)}"}), 500

        else:
            return jsonify({"error": "File format not supported"}), 400

    except Exception as e:
        logger.error(f"Error in load_file: {e}", exc_info=True)
        return jsonify({"error": f"Failed to process file: {str(e)}"}), 500

# Global storage for background task results
task_results = {}

@app.route("/task_result/<task_id>", methods=["GET"])
def get_task_result(task_id):
    """Get the result of a background task"""
    if task_id in task_results:
        result = task_results[task_id]
        # Clean up after retrieval
        del task_results[task_id]
        return jsonify(result)
    else:
        return jsonify({"error": "Task not found or still processing"}), 404

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
    """Generate meeting summary using AI (NOT saving to ChromaDB yet)"""
    try:
        logger.info("SUMMARIZE ENDPOINT CALLED")
        
        if not client:
            logger.error("OpenAI client not available")
            return jsonify({"error": "AI service not available"}), 503

        data = request.json
        text = data.get("text", "") if data else ""
        
        if not text or len(text) < 10:
            logger.error("Text too short or missing")
            return jsonify({"error": "Text too short to summarize"}), 400

        logger.info("Generating meeting summary...")

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

        response = client.chat.completions.create(
            model="gpt-4o-mini",
            messages=[
                {"role": "system", "content": "You are a helpful assistant specialized in summarizing meeting notes."},
                {"role": "user", "content": prompt}
            ],
            temperature=0
        )
        
        summary = response.choices[0].message.content.strip()
        meeting_title = generate_meeting_title(text)
        meeting_date = parse_date_from_text(text)
        
        # Store in session for later saving (when user clicks "Lưu")
        session["pending_summary"] = {
            "summary": summary,
            "title": meeting_title,
            "date": meeting_date,
            "original_text": text
        }
        
        logger.info("Summary generated successfully (not saved to ChromaDB yet)")
        
        return jsonify({
            "success": True,
            "summary": summary,
            "title": meeting_title,
            "date": meeting_date
        })
    
    except Exception as e:
        logger.error(f"ERROR in summarize endpoint: {e}", exc_info=True)
        return jsonify({"error": f"Failed to generate summary: {str(e)}"}), 500

@app.route("/save_summary", methods=["POST"])
def save_summary():
    """Save the edited summary to file AND ChromaDB"""
    try:
        logger.info("="*80)
        logger.info("SAVE_SUMMARY ENDPOINT CALLED")
        logger.info("="*80)
        
        data = request.json
        summary = data.get("summary", "")
        title = data.get("title", "")
        date = data.get("date", "")
        
        pending = session.get("pending_summary", {})
        if not summary and pending:
            summary = pending.get("summary", "")
        if not title and pending:
            title = pending.get("title", "Meeting")
        if not date and pending:
            date = pending.get("date", datetime.now().strftime("%Y-%m-%d"))
        
        original_text = pending.get("original_text", "")
        
        # Allow user to edit title
        if data.get("title"):
            title = data.get("title")
        
        if not summary:
            return jsonify({"error": "No summary to save"}), 400
        
        logger.info(f"Saving summary: title={title}, date={date}")
        
        timestamp = datetime.now().strftime("%H%M%S")
        safe_title = sanitize_filename(title)
        base_filename = f"{date}_{timestamp}_{safe_title}"
        
        ensure_directories()
        output_file = get_unique_filename(
            os.path.join(Config.OUTPUT_DIR, base_filename),
            ".txt"
        )
        
        meeting_record = f"""
{'='*80}
MEETING SUMMARY
{'='*80}
Title: {title}
Date: {date}
Generated: {datetime.now().strftime("%Y-%m-%d %H:%M:%S")}
{'='*80}

{summary.strip()}

{'='*80}
"""
        
        # Save to file
        with open(output_file, "w", encoding="utf-8") as f:
            f.write(meeting_record)

        logger.info(f"Summary saved to file: {output_file}")
        
        filename = os.path.basename(output_file)
        
        # ⭐ SAVE TO CHROMADB
        logger.info("Attempting to save to ChromaDB...")
        chromadb_saved = save_summary_to_chromadb(
            summary=summary,
            title=title,
            date=date,
            original_text=original_text,
            filename=filename
        )
        
        if chromadb_saved:
            logger.info("✅ Successfully saved to ChromaDB")
        else:
            logger.error("❌ Failed to save to ChromaDB")
        
        session.pop("pending_summary", None)
        
        return jsonify({
            "success": True,
            "message": "Summary saved successfully",
            "filename": filename,
            "title": title,
            "date": date,
            "chromadb_saved": chromadb_saved
        })
    
    except Exception as e:
        logger.error(f"Error in save_summary: {e}", exc_info=True)
        return jsonify({"error": f"Failed to save summary: {str(e)}"}), 500

@app.route("/chatbot", methods=["POST"])
def chatbot():
    try:
        if not client:
            return jsonify({"error": "AI service unavailable"}), 503

        data = request.json
        question = data.get("question", "").strip()
        if not question:
            return jsonify({"error": "No question provided"}), 400

        chat_history = session.get("chat_history", [])

        # --- STEP 1: Classify question ---
        now = datetime.now()
        year = now.year
        month = now.month
        
        function_spec = {
            "name": "classify_question",
            "description": "Determine whether the question is about a date or a topic",
            "parameters": {
                "type": "object",
                "properties": {
                    "type": {"type": "string", "enum": ["date", "topic"]},
                    "date": {"type": "string", "description": f"The date in YYYY-MM-DD format. If content just has day, set month is {month} and year is {year}."}
                },
                "required": ["type"]
            }
        }

        response = client.chat.completions.create(
            model="gpt-4o-mini",
            messages=[
                {"role": "system", "content": "You are a classifier for user questions about meetings."},
                {"role": "user", "content": question}
            ],
            functions=[function_spec],
            function_call="auto",
            max_tokens=100,
            temperature=0
        )

        call = response.choices[0].message
        classification = {"type": "topic", "date": None}

        if hasattr(call, "function_call") and call.function_call:
            args_str = call.function_call.arguments
            if isinstance(args_str, str):
                try:
                    args = json.loads(args_str)
                    classification.update(args)
                except json.JSONDecodeError:
                    logger.warning(f"⚠️ Failed to parse arguments: {args_str}")

        logger.info(f"🧩 Classified as: {classification}")

        # --- STEP 2: Search with ChromaDB ---
        date_filter = classification.get("date") if classification["type"] == "date" else None
        search_results = search_meetings_chromadb(question, n_results=5, date_filter=date_filter)

        # --- STEP 3: Build enhanced context with full meeting details ---
        context = ""
        meeting_details = []
        
        if search_results:
            context = "📋 Relevant meeting information found:\n\n"
            for idx, result in enumerate(search_results):
                meta = result["metadata"]
                summary = result['summary']
                
                # Store meeting details for reference
                meeting_info = {
                    "index": idx + 1,
                    "title": meta['title'],
                    "date": meta['date'],
                    "filename": meta.get('filename', ''),
                    "id": result['id'],
                    "relevance": round((1 - result.get('distance', 0)) * 100, 1) if result.get('distance') is not None else 100
                }
                meeting_details.append(meeting_info)
                
                # Add full summary to context (not truncated)
                context += f"[Meeting {idx + 1}]\n"
                context += f"Title: {meta['title']}\n"
                context += f"Date: {meta['date']}\n"
                context += f"Relevance: {meeting_info['relevance']}%\n"
                context += f"Content:\n{summary}\n"
                context += f"{'-'*80}\n\n"

        # --- STEP 4: Generate enhanced answer ---
        system_prompt = f"""You are a helpful meeting assistant that provides detailed, accurate answers about meetings.

When answering questions:
1. Use the meeting information provided in the context
2. If specific meetings are relevant, mention them by title and date
3. Quote or reference specific details from the meetings when applicable
4. If multiple meetings contain relevant information, summarize findings from each
5. Always provide clear, well-structured answers in Vietnamese
6. If the context doesn't contain the information needed, politely say so

Available Context:
{context if context else "No meeting data available yet."}
"""

        messages = [{"role": "system", "content": system_prompt}]
        messages.extend(chat_history[-10:])
        messages.append({"role": "user", "content": question})

        answer_response = client.chat.completions.create(
            model="gpt-4o-mini",
            messages=messages,
            temperature=0.3,
            max_tokens=1500
        )

        raw_answer = answer_response.choices[0].message.content or "Xin lỗi, tôi không chắc cách trả lời câu hỏi đó."
        # --- STEP 5: Format response with meeting references ---
        formatted_answer = f"{raw_answer.strip()}\n"

        # --- STEP 6: Update chat history ---
        chat_history.append({"role": "user", "content": question})
        chat_history.append({"role": "assistant", "content": formatted_answer})
        session["chat_history"] = chat_history[-20:]

        return jsonify({
            "answer": formatted_answer,
            "classification": classification,
            "meetings": meeting_details,
            "count": len(search_results)
        })

    except Exception as e:
        logger.error(f"Error in chatbot: {e}", exc_info=True)
        return jsonify({"error": "Failed to process question"}), 500
    
@app.route("/list_meetings", methods=["GET"])
def list_meetings():
    """List all available meeting summaries from ChromaDB"""
    try:
        dates = get_all_meeting_dates_chromadb()
        
        meetings = []
        grouped_meetings = {}
        
        for date in dates:
            date_meetings = get_meeting_by_date_chromadb(date)
            grouped_meetings[date] = []
            
            for meeting in date_meetings:
                metadata = meeting['metadata']
                meeting_info = {
                    "date": metadata['date'],
                    "title": metadata['title'],
                    "filename": metadata['filename'],
                    "created": metadata.get('created_at', ''),
                    "id": meeting['id']
                }
                meetings.append(meeting_info)
                grouped_meetings[date].append(meeting_info)
        
        return jsonify({
            "meetings": meetings,
            "grouped": grouped_meetings,
            "total": len(meetings)
        })
    
    except Exception as e:
        logger.error(f"Error listing meetings: {e}")
        return jsonify({"error": "Failed to list meetings"}), 500

@app.route("/search_meetings", methods=["POST"])
def search_meetings():
    """Search meetings using semantic search"""
    try:
        data = request.json
        query = data.get("query", "").strip()
        n_results = data.get("n_results", 5)
        
        if not query:
            return jsonify({"error": "No search query provided"}), 400
        
        results = search_meetings_chromadb(query, n_results=n_results)
        
        formatted_results = []
        for result in results:
            formatted_results.append({
                "id": result['id'],
                "title": result['metadata']['title'],
                "date": result['metadata']['date'],
                "summary": result['summary'][:300] + "...",
                "relevance": 1 - result['distance'] if result['distance'] else 1.0
            })
        
        return jsonify({
            "success": True,
            "results": formatted_results,
            "total": len(formatted_results)
        })
    
    except Exception as e:
        logger.error(f"Error searching meetings: {e}")
        return jsonify({"error": "Failed to search meetings"}), 500

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
    app.run(debug=True, host='0.0.0.0', port=5000)