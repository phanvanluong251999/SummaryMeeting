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
import uuid

# -------- RAG UTILITIES IMPORT --------
from rag_enhancements import (
    count_tokens,
    truncate_context_intelligently,
    validate_answer_grounding,
    add_validation_disclaimer
)

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

# -------- LANGCHAIN TEXT SPLITTERS --------
try:
    from langchain_text_splitters import RecursiveCharacterTextSplitter
    langchain_available = True
    logger.info("✅ LangChain text splitters available")
except ImportError:
    langchain_available = False
    logger.warning("⚠️ LangChain not available - install with: pip install langchain langchain-text-splitters")

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
    # Get ChromaDB mode from environment
    chroma_mode = os.environ.get('CHROMA_MODE', 'local').lower()

    # Initialize ChromaDB client based on mode
    if chroma_mode == 'cloud':
        # Cloud mode: Connect to remote ChromaDB server
        chroma_host = os.environ.get('CHROMA_HOST', 'localhost')
        chroma_port = int(os.environ.get('CHROMA_PORT', 8000))

        logger.info(f"🌐 Connecting to ChromaDB server at {chroma_host}:{chroma_port}")
        chroma_client = chromadb.HttpClient(host=chroma_host, port=chroma_port)
        logger.info(f"✅ Connected to cloud ChromaDB server")
    else:
        # Local mode: Use persistent local storage
        logger.info(f"💾 Using local ChromaDB at {Config.CHROMA_DIR}")
        chroma_client = chromadb.PersistentClient(path=Config.CHROMA_DIR)
        logger.info(f"✅ Connected to local ChromaDB")

    # Use text-embedding-3-small for better search accuracy
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

    logger.info(f"✅ ChromaDB initialized (mode: {chroma_mode}). Current count: {meeting_collection.count()}")
except Exception as e:
    logger.error(f"Failed to initialize ChromaDB: {e}")
    import traceback
    logger.error(traceback.format_exc())
    chroma_client = None
    meeting_collection = None

# -------- INITIALIZATION COMPLETE --------
logger.info(f"✅ Application initialized. ChromaDB count: {meeting_collection.count() if meeting_collection else 0}")

# -------- METADATA EXTRACTION HELPERS --------
def extract_key_topics(summary: str, max_topics: int = 5) -> List[str]:
    """
    Extract key topics from summary using AI-powered extraction with chunking
    """
    try:
        if not client:
            # Fallback to simple keyword extraction
            return extract_topics_fallback(summary, max_topics)

        # ⭐ NEW: Use AI to extract topics more accurately
        prompt = f"""Extract the {max_topics} most important topics/keywords from this meeting summary.
Return ONLY a comma-separated list of topics (single words or short phrases), nothing else.
Focus on: main subjects discussed, technologies mentioned, project names, key concepts.

Summary:
{summary[:2000]}

Format: topic1, topic2, topic3, topic4, topic5"""

        response = client.chat.completions.create(
            model="gpt-4o-mini",
            messages=[
                {"role": "system", "content": "You extract key topics from meeting summaries. Return only comma-separated topics."},
                {"role": "user", "content": prompt}
            ],
            temperature=0,
            max_tokens=100
        )

        topics_str = response.choices[0].message.content.strip()
        topics = [t.strip() for t in topics_str.split(',') if t.strip()][:max_topics]

        return topics if topics else extract_topics_fallback(summary, max_topics)

    except Exception as e:
        logger.error(f"Error extracting topics with AI: {e}")
        return extract_topics_fallback(summary, max_topics)


def extract_topics_fallback(summary: str, max_topics: int = 5) -> List[str]:
    """Fallback: Simple keyword extraction without AI"""
    try:
        stopwords = {
            'the', 'a', 'an', 'and', 'or', 'but', 'in', 'on', 'at', 'to', 'for',
            'của', 'và', 'là', 'có', 'được', 'này', 'đó', 'các', 'cho', 'về'
        }

        words = re.findall(r'\b[a-zA-ZàáảãạâầấẩẫậăằắẳẵặèéẻẽẹêềếểễệìíỉĩịòóỏõọôồốổỗộơờớởỡợùúủũụưừứửữựỳýỷỹỵđĐ]{2,}\b', summary.lower())
        word_freq = {}

        for word in words:
            if word not in stopwords:
                word_freq[word] = word_freq.get(word, 0) + 1

        topics = sorted(word_freq.items(), key=lambda x: x[1], reverse=True)[:max_topics]
        return [topic[0] for topic in topics]

    except Exception as e:
        logger.error(f"Error in fallback topic extraction: {e}")
        return []

def chunk_text_for_metadata(text: str, chunk_size: int = 2000, chunk_overlap: int = 200) -> List[str]:
    """
    Split text into chunks for better metadata extraction using LangChain

    Args:
        text: Text to split
        chunk_size: Maximum characters per chunk
        chunk_overlap: Overlap between chunks to preserve context

    Returns:
        List of text chunks
    """
    try:
        if not langchain_available:
            # Fallback: Simple chunking if LangChain not available
            chunks = []
            for i in range(0, len(text), chunk_size - chunk_overlap):
                chunks.append(text[i:i + chunk_size])
            return chunks

        # Use LangChain's RecursiveCharacterTextSplitter for smart chunking
        text_splitter = RecursiveCharacterTextSplitter(
            chunk_size=chunk_size,
            chunk_overlap=chunk_overlap,
            length_function=len,
            separators=["\n\n", "\n", ". ", " ", ""]  # Try to split at natural boundaries
        )

        chunks = text_splitter.split_text(text)
        logger.info(f"📄 Split text into {len(chunks)} chunks for better metadata extraction")
        return chunks

    except Exception as e:
        logger.error(f"Error chunking text: {e}")
        # Fallback to full text
        return [text]


def extract_participants_with_roles(text: str, summary: str = "") -> List[Dict[str, str]]:
    """
    Extract participant names with their roles from "Attendees:", "Participants:" sections.
    Returns: [{"name": "Dev A", "role": "Developer"}]
    """
    try:
        participants = {}

        # ⭐ IMPROVED: Look for participant sections by keywords
        combined_text = text + "\n" + summary

        # Find sections with participant lists
        participant_section_patterns = [
            r'(?:Attendees?|Participants?|People|Người tham gia|Thành viên)[:\s]*\n((?:[-•*]\s*.*\n?)+)',
            r'(?:Attendees?|Participants?|People|Người tham gia|Thành viên)[:\s]*((?:[-•*]\s*[^\n]+\n?)+)',
        ]

        participant_section = ""
        for pattern in participant_section_patterns:
            match = re.search(pattern, combined_text, re.IGNORECASE | re.MULTILINE)
            if match:
                participant_section = match.group(1)
                logger.info(f"📋 Found participant section: {len(participant_section)} chars")
                break

        # If section found, extract names with roles from list format
        if participant_section:
            # Pattern: "- Dev A (Developer)" or "- PM Nam (Project Manager)"
            list_patterns = [
                r'[-•*]\s*([A-Z][A-Za-z0-9\s]+?)\s*\(([^)]+)\)',  # "- Dev A (Developer)"
                r'[-•*]\s*([A-Z][A-Za-z0-9àáảãạâầấẩẫậăằắẳẵặèéẻẽẹêềếểễệìíỉĩịòóỏõọôồốổỗộơờớởỡợùúủũụưừứửữựỳýỷỹỵđ\s]+?):\s*([^\n]+)',  # "- Dev A: Developer"
            ]

            for pattern in list_patterns:
                matches = re.findall(pattern, participant_section)
                for match in matches:
                    name = match[0].strip()
                    role = match[1].strip()

                    # Clean up name (remove extra spaces, numbers at end)
                    name = re.sub(r'\s+', ' ', name)

                    if name not in participants:
                        participants[name] = {"name": name, "role": role}
                        logger.info(f"  👤 Found: {name} ({role})")

        # Fallback: If no section found, look for role-based patterns anywhere in text
        if not participants:
            chunks = chunk_text_for_metadata(combined_text, chunk_size=1500, chunk_overlap=300)

            for chunk in chunks:
                # Pattern: "Dev A", "PM Nam", "Tester Linh", etc.
                role_name_patterns = [
                    (r'\b(Dev|Developer)\s+([A-Z][A-Za-z0-9]*)\b', 'Developer'),
                    (r'\b(PM|Project Manager)\s+([A-Z][A-Za-zàáảãạâầấẩẫậăằắẳẵặèéẻẽẹêềếểễệìíỉĩịòóỏõọôồốổỗộơờớởỡợùúủũụưừứửữựỳýỷỹỵđ]+)\b', 'Project Manager'),
                    (r'\b(Tester|QA|QC)\s+([A-Z][A-Za-zàáảãạâầấẩẫậăằắẳẵặèéẻẽẹêềếểễệìíỉĩịòóỏõọôồốổỗộơờớởỡợùúủũụưừứửữựỳýỷỹỵđ]+)\b', 'Tester'),
                    (r'\b(Designer|Thiết kế)\s+([A-Z][A-Za-zàáảãạâầấẩẫậăằắẳẵặèéẻẽẹêềếểễệìíỉĩịòóỏõọôồốổỗộơờớởỡợùúủũụưừứửữựỳýỷỹỵđ]+)\b', 'Designer'),
                ]

                for pattern, role in role_name_patterns:
                    matches = re.findall(pattern, chunk, re.IGNORECASE)
                    for match in matches:
                        role_prefix = match[0]
                        name_part = match[1]
                        full_name = f"{role_prefix} {name_part}"

                        if full_name not in participants:
                            participants[full_name] = {"name": full_name, "role": role}

        result = list(participants.values())
        logger.info(f"✅ Extracted {len(result)} participants")
        return result

    except Exception as e:
        logger.error(f"Error extracting participants: {e}")
        return []

def detect_language(text: str) -> str:
    """Simple language detection (Vietnamese vs English)"""
    try:
        vietnamese_chars = re.findall(r'[àáảãạâầấẩẫậăằắẳẵặèéẻẽẹêềếểễệìíỉĩịòóỏõọôồốổỗộơờớởỡợùúủũụưừứửữựỳýỷỹỵđĐ]', text)
        # If more than 5% of characters are Vietnamese-specific, it's Vietnamese
        if len(vietnamese_chars) / max(len(text), 1) > 0.05:
            return "vi"
        return "en"
    except Exception as e:
        logger.error(f"Error detecting language: {e}")
        return "unknown"

def extract_actual_duration(text: str, summary: str = "") -> dict:
    """
    Extract actual meeting duration from time ranges like "10:00 AM - 11:00 AM" = 60 minutes.
    Returns: {"minutes": int, "start_time": str, "end_time": str, "source": str}
    """
    try:
        result = {
            "minutes": 0,
            "start_time": None,
            "end_time": None,
            "source": "unknown"
        }

        # Look for "Time:" section first
        combined_text = summary + " " + text[:2000]

        # ⭐ IMPROVED: Look for Time: section with time range
        time_section_patterns = [
            r'Time[:\s]*(\d{1,2}:\d{2}\s*(?:AM|PM)?)\s*[-–]\s*(\d{1,2}:\d{2}\s*(?:AM|PM)?)',
            r'Thời gian[:\s]*(\d{1,2}:\d{2}\s*(?:AM|PM)?)\s*[-–]\s*(\d{1,2}:\d{2}\s*(?:AM|PM)?)',
        ]

        def parse_time_with_ampm(time_str):
            """Parse time string like '9:00 AM' or '10:30 PM' to 24-hour format"""
            time_str = time_str.strip()

            # Check for AM/PM
            is_pm = 'PM' in time_str.upper()
            is_am = 'AM' in time_str.upper()

            # Remove AM/PM and parse
            time_str = re.sub(r'\s*(AM|PM)', '', time_str, flags=re.IGNORECASE).strip()
            parts = time_str.split(':')

            hour = int(parts[0])
            minute = int(parts[1]) if len(parts) > 1 else 0

            # Convert to 24-hour format
            if is_pm and hour != 12:
                hour += 12
            elif is_am and hour == 12:
                hour = 0

            return hour, minute

        # Try to find time range in format "9:00 AM - 10:30 AM"
        for pattern in time_section_patterns:
            match = re.search(pattern, combined_text, re.IGNORECASE)
            if match:
                start_str = match.group(1)
                end_str = match.group(2)

                try:
                    start_hour, start_min = parse_time_with_ampm(start_str)
                    end_hour, end_min = parse_time_with_ampm(end_str)

                    # Calculate duration
                    start_total = start_hour * 60 + start_min
                    end_total = end_hour * 60 + end_min

                    # Handle crossing midnight
                    if end_total < start_total:
                        end_total += 24 * 60

                    duration = end_total - start_total

                    if 5 <= duration <= 480:  # 5 min to 8 hours
                        result["minutes"] = duration
                        result["start_time"] = f"{start_hour:02d}:{start_min:02d}"
                        result["end_time"] = f"{end_hour:02d}:{end_min:02d}"
                        result["source"] = "time_section"
                        logger.info(f"⏱️  Calculated from time range: {start_str} - {end_str} = {duration} minutes")
                        return result

                except Exception as e:
                    logger.warning(f"Failed to parse time: {e}")
                    continue

        # Fallback: Look for patterns anywhere in text (without AM/PM)
        combined_lower = combined_text.lower()

        # Pattern 1: Direct duration mentions
        duration_patterns = [
            (r'(\d+)\s*(?:phút|minutes?|mins?)\b', 1),
            (r'(\d+)\s*(?:giờ|hours?|hrs?)\b', 60),
            (r'lasted\s+(\d+)\s*(?:min|minutes?)', 1),
            (r'kéo dài\s*(?:khoảng\s*)?(\d+)\s*(?:phút|minutes?)', 1),
        ]

        for pattern, multiplier in duration_patterns:
            matches = re.findall(pattern, combined_lower)
            if matches:
                duration_value = int(matches[0])
                result["minutes"] = duration_value * multiplier
                result["source"] = "explicit_mention"
                logger.info(f"⏱️  Found explicit duration: {result['minutes']} minutes")
                return result

        # Pattern 2: Time range without AM/PM (e.g., "9:00 - 10:30")
        time_range_patterns = [
            r'(\d{1,2})[:\.](\d{2})\s*(?:-|đến|to)\s*(\d{1,2})[:\.](\d{2})',
            r'(\d{1,2})h(\d{2})\s*(?:-|đến|to)\s*(\d{1,2})h(\d{2})',
        ]

        for pattern in time_range_patterns:
            matches = re.search(pattern, combined_lower)
            if matches:
                start_hour = int(matches.group(1))
                start_min = int(matches.group(2))
                end_hour = int(matches.group(3))
                end_min = int(matches.group(4))

                start_total = start_hour * 60 + start_min
                end_total = end_hour * 60 + end_min

                if end_total < start_total:
                    end_total += 24 * 60

                duration = end_total - start_total

                if 5 <= duration <= 480:
                    result["minutes"] = duration
                    result["start_time"] = f"{start_hour:02d}:{start_min:02d}"
                    result["end_time"] = f"{end_hour:02d}:{end_min:02d}"
                    result["source"] = "time_range"
                    logger.info(f"⏱️  Calculated: {result['start_time']} - {result['end_time']} = {duration} min")
                    return result

        # Fallback: Estimate from word count
        if result["minutes"] == 0:
            word_count = len(text.split())
            result["minutes"] = max(1, word_count // 150)
            result["source"] = "estimated"
            logger.info(f"⏱️  Estimated from word count: ~{result['minutes']} minutes")

        return result

    except Exception as e:
        logger.error(f"Error extracting duration: {e}")
        return {"minutes": 0, "start_time": None, "end_time": None, "source": "error"}

def extract_individual_actions(summary: str, text: str = "") -> List[Dict[str, str]]:
    """
    Extract specific actions assigned to each person using CHUNKING for better accuracy.
    Returns: [{"person": "Dev A", "action": "Hoàn thiện API authentication", "deadline": "2024-12-01"}]
    """
    try:
        actions = []

        # ⭐ NEW: Process both summary and text chunks
        chunks = chunk_text_for_metadata(text, chunk_size=1500, chunk_overlap=300) if text else []

        # Process summary + each chunk
        texts_to_process = [summary] + chunks

        for combined_text in texts_to_process:
            # Pattern 1: "Person sẽ làm X" / "Person will do X"
            action_patterns = [
                r'([A-Z][a-zàáảãạâầấẩẫậăằắẳẵặèéẻẽẹêềếểễệìíỉĩịòóỏõọôồốổỗộơờớởỡợùúủũụưừứửữựỳýỷỹỵđ\s]+(?:A|B|C|D)?)\s+(?:sẽ|phải|cần|will|must|should)\s+([^.!?\n]{10,100})',
                r'([A-Z][a-zàáảãạâầấẩẫậăằắẳẵặèéẻẽẹêềếểễệìíỉĩịòóỏõọôồốổỗộơờớởỡợùúủũụưừứửữựỳýỷỹỵđ\s]+(?:A|B|C|D)?)\s+(?:phụ trách|responsible for|in charge of)\s+([^.!?\n]{10,100})',
                r'-\s*([A-Z][a-zàáảãạâầấẩẫậăằắẳẵặèéẻẽẹêềếểễệìíỉĩịòóỏõọôồốổỗộơờớởỡợùúủũụưừứửữựỳýỷỹỵđ\s]+):\s*([^.!?\n]{10,150})',
            ]

            for pattern in action_patterns:
                matches = re.findall(pattern, combined_text, re.IGNORECASE)
                for match in matches:
                    person = match[0].strip()
                    action = match[1].strip()

                    # ⭐ FIX: Skip pronouns and generic words
                    person_lower = person.lower().strip()

                    # List of pronouns and generic words to skip (Vietnamese + English)
                    skip_words = [
                        'meeting', 'summary', 'họp', 'cuộc',
                        'tôi', 'bạn', 'chúng tôi', 'anh ấy', 'cô ấy', 'họ',  # Vietnamese pronouns
                        'i', 'you', 'we', 'he', 'she', 'they', 'it',          # English pronouns
                        'time', 'thời gian', 'người tham gia', 'participants',
                        'deadline', 'hạn chót', 'timeline'
                    ]

                    # Skip if it's a pronoun or too generic
                    if person_lower in skip_words or len(person) > 50 or len(person) < 3:
                        continue

                    # Skip if person doesn't look like a name (should start with capital or have role keyword)
                    has_role_keyword = any(keyword in person_lower for keyword in ['dev', 'pm', 'tester', 'designer', 'ba', 'qa'])
                    starts_with_capital = person[0].isupper()

                    if not (starts_with_capital or has_role_keyword):
                        continue

                    # ⭐ IMPROVED: Better deadline extraction for Vietnamese dates
                    deadline = None
                    if action in combined_text:
                        action_context = combined_text[max(0, combined_text.find(action) - 100):combined_text.find(action) + len(action) + 150]

                        # Multiple deadline patterns (Vietnamese + English)
                        deadline_patterns = [
                            r'(?:deadline|hạn chót|đến|by|before|vào)\s+(\d{1,2}[/-]\d{1,2}[/-]?\d{0,4})',  # "vào 10/10" or "deadline 10/10/2025"
                            r'(?:deadline|hạn chót|đến|by|before|vào)\s+(\d{4}-\d{2}-\d{2})',  # "2025-10-10"
                            r'hoàn thành vào\s+(\d{1,2}[/-]\d{1,2})',  # "hoàn thành vào 10/10"
                        ]

                        for deadline_pattern in deadline_patterns:
                            deadline_match = re.search(deadline_pattern, action_context.lower())
                            if deadline_match:
                                deadline = deadline_match.group(1)
                                break

                    # Check for duplicates before adding
                    action_key = f"{person}:{action}"
                    if not any(f"{a['person']}:{a['action']}" == action_key for a in actions):
                        actions.append({
                            "person": person,
                            "action": action,
                            "deadline": deadline
                        })

        # Limit to top 10 actions
        return actions[:10]

    except Exception as e:
        logger.error(f"Error extracting individual actions: {e}")
        return []

def detect_meeting_type(summary: str, original_text: str) -> str:
    """Detect meeting type from summary and text"""
    try:
        combined_text = (summary + " " + original_text[:500]).lower()

        # Meeting type patterns
        types = {
            "standup": ["standup", "daily", "stand-up", "scrum", "hàng ngày", "điểm danh"],
            "review": ["review", "đánh giá", "xem xét", "retrospective", "retro"],
            "planning": ["planning", "kế hoạch", "lập kế hoạch", "sprint planning"],
            "brainstorm": ["brainstorm", "ý tưởng", "brainstorming", "sáng tạo"],
            "decision": ["decision", "quyết định", "approve", "phê duyệt"],
            "training": ["training", "đào tạo", "workshop", "học tập"],
            "onboarding": ["onboarding", "giới thiệu", "orientation"],
            "interview": ["interview", "phỏng vấn", "candidate"],
            "client": ["client", "khách hàng", "customer", "partner", "đối tác"],
            "budget": ["budget", "ngân sách", "financial", "tài chính", "cost", "chi phí"],
        }

        for meeting_type, keywords in types.items():
            for keyword in keywords:
                if keyword in combined_text:
                    return meeting_type

        return "general"
    except Exception as e:
        logger.error(f"Error detecting meeting type: {e}")
        return "general"

# -------- CHROMADB HELPER FUNCTIONS --------
def save_summary_to_chromadb(
    summary: str,
    title: str,
    date: str,
    original_text: str,
    filename: str
) -> bool:
    """Save meeting summary to ChromaDB for semantic search with enhanced metadata"""
    try:
        if not meeting_collection:
            logger.warning("ChromaDB collection not available")
            return False

        # ⭐ FIX: Create unique ID with timestamp + UUID to guarantee no overwrites
        timestamp = int(datetime.now().timestamp())
        unique_id = str(uuid.uuid4())[:8]  # Short UUID suffix for uniqueness
        safe_filename = filename.replace('.txt', '')
        doc_id = f"{date}_{timestamp}_{unique_id}_{safe_filename}"

        logger.info(f"Attempting to save to ChromaDB with ID: {doc_id}")

        # ⭐ ENHANCEMENT: Extract comprehensive metadata focused on people and actions
        topics = extract_key_topics(summary)
        participants_with_roles = extract_participants_with_roles(original_text, summary)
        language = detect_language(original_text)
        duration_info = extract_actual_duration(original_text, summary)
        individual_actions = extract_individual_actions(summary, original_text)
        meeting_type = detect_meeting_type(summary, original_text)

        # Format participants for storage
        participants_str = ", ".join([p["name"] for p in participants_with_roles])
        participant_roles = {p["name"]: p["role"] for p in participants_with_roles if p["role"]}

        # Format actions for storage
        actions_summary = []
        for action in individual_actions:
            action_str = f"{action['person']}: {action['action']}"
            if action.get('deadline'):
                action_str += f" (deadline: {action['deadline']})"
            actions_summary.append(action_str)

        # ⭐ NEW METADATA STRUCTURE: Focused on time, people, and individual actions
        # ⭐ FIX: Ensure all metadata values are ChromaDB-compatible types (bool, int, float, str)
        metadata = {
            # === Basic Information ===
            "title": str(title),
            "date": str(date),
            "filename": str(filename),
            "created_at": datetime.now().isoformat(),

            # === Meeting Classification ===
            "meeting_type": str(meeting_type),
            "language": str(language),

            # === Time Information (NEW - IMPROVED) ===
            "duration_minutes": int(duration_info["minutes"]),
            "duration_source": str(duration_info["source"]),
            # ChromaDB fix: Use "N/A" instead of empty string
            "start_time": str(duration_info.get("start_time") or "N/A"),
            "end_time": str(duration_info.get("end_time") or "N/A"),
            "is_short_meeting": bool(duration_info["minutes"] < 30),
            "is_long_meeting": bool(duration_info["minutes"] > 90),

            # === People & Participation (NEW - IMPROVED) ===
            "participants": str(participants_str) if participants_str else "N/A",
            "participant_count": int(len(participants_with_roles)),
            "participant_roles": str(json.dumps(participant_roles, ensure_ascii=False)),
            "has_multiple_speakers": bool(len(participants_with_roles) > 2),

            # === Individual Actions (NEW - KEY FEATURE) ===
            "individual_actions": str(" | ".join(actions_summary)) if actions_summary else "N/A",
            "action_count": int(len(individual_actions)),
            "has_actions": bool(len(individual_actions) > 0),

            # === Content Metrics ===
            "text_length": int(len(original_text)),
            "summary_length": int(len(summary)),
            "word_count": int(len(original_text.split())),
            "topics": str(", ".join(topics)) if topics else "N/A",
        }

        logger.info(f"📋 Enhanced Metadata Extracted:")
        logger.info(f"  🏷️  Type: {meeting_type}")
        logger.info(f"  📊 Topics: {topics}")

        # Format participants list
        participants_display = [f"{p['name']} ({p['role']})" if p['role'] else p['name'] for p in participants_with_roles]
        logger.info(f"  👥 Participants ({len(participants_with_roles)}): {participants_display}")
        logger.info(f"  🌐 Language: {language}")
        logger.info(f"  ⏱️  Duration: {duration_info['minutes']} min (source: {duration_info['source']})")
        if duration_info.get("start_time"):
            logger.info(f"  🕐 Time: {duration_info['start_time']} - {duration_info['end_time']}")
        logger.info(f"  📝 Individual actions ({len(individual_actions)}):")
        for action in individual_actions: 
            logger.info(f"      • {action['person']}: {action['action'][:60]}...")

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
    date_filter: Optional[str] = None,
    meeting_type: Optional[str] = None,
    priority: Optional[str] = None,
    has_decisions: Optional[bool] = None,
    has_action_items: Optional[bool] = None
) -> List[Dict]:
    """
    Search meetings using semantic similarity with advanced metadata filtering

    Args:
        query: Search query text
        n_results: Number of results to return
        date_filter: Filter by specific date (YYYY-MM-DD)
        meeting_type: Filter by meeting type (standup, review, planning, etc.)
        priority: Filter by priority (high, medium, normal)
        has_decisions: Filter meetings with/without decisions
        has_action_items: Filter meetings with/without action items
    """
    try:
        if not meeting_collection:
            logger.warning("ChromaDB collection not available")
            return []

        # ⭐ Build advanced where filter with metadata
        where_filter = {}

        if date_filter:
            where_filter["date"] = date_filter

        if meeting_type:
            where_filter["meeting_type"] = meeting_type

        if priority:
            where_filter["priority"] = priority

        if has_decisions is not None:
            where_filter["has_decisions"] = has_decisions

        if has_action_items is not None:
            where_filter["has_action_items"] = has_action_items

        # Log filter being applied
        if where_filter:
            logger.info(f"🔍 Applying filters: {where_filter}")

        # Perform semantic search with filters
        results = meeting_collection.query(
            query_texts=[query],
            n_results=n_results,
            where=where_filter if where_filter else None
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

        logger.info(f"✅ ChromaDB search found {len(formatted_results)} results")
        return formatted_results

    except Exception as e:
        logger.error(f"❌ Error searching ChromaDB: {e}")
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

# -------- QUERY INTENTION CLASSIFIER --------
def classify_query_intention(
    question: str,
    conversation_context: str = "",
    chat_history: List[Dict] = None
) -> Dict:
    """
    Classify the intention/purpose of a query to enable more targeted result filtering.

    NEW: Also detects if this is a FOLLOW-UP question (about current meeting)
    vs a NEW SEARCH query (searching across meetings).

    Returns:
    {
        "intention_type": "person_focused|task_focused|...|topic_focused",
        "confidence": float (0-1),
        "is_followup_question": bool,  # NEW: True if follow-up, False if new search
        "extracted_entities": {...},
        "should_filter_metadata": {...},
        "reasoning": str
    }
    """
    try:
        # Define intention patterns (Vietnamese + English)
        person_keywords = [
            'dev', 'pm', 'tester', 'designer', 'ba', 'qa', 'lead', 'manager',
            'gì', 'người nào', 'ai là', 'thế nào', 'của ai',
            'what did', 'did', 'who is', 'which', 'người', 'tên', 'name'
        ]

        task_keywords = [
            'task', 'action', 'nhiệm vụ', 'công việc', 'làm gì', 'sẽ làm', 'cần làm',
            'assign', 'responsible', 'phụ trách', 'đảm bảo', 'hoàn thành',
            'what to do', 'what should', 'need to', 'have to', 'deadline'
        ]

        decision_keywords = [
            'decide', 'decision', 'quyết định', 'phê duyệt', 'đồng ý', 'không đồng ý',
            'approved', 'rejected', 'conclusion', 'kết luận',
            'agreed', 'disagreed', 'finalize', 'finalized'
        ]

        time_keywords = [
            'duration', 'long', 'thời gian', 'bao lâu', 'kéo dài', 'phút', 'giờ',
            'start', 'end', 'begin', 'finished', 'started at', 'ended at',
            'how long', 'what time', 'when', 'schedule'
        ]

        participant_keywords = [
            'participant', 'attendee', 'người tham gia', 'có ai', 'who attended',
            'who was there', 'who joined', 'attending', 'present', 'số lượng'
        ]

        comparison_keywords = [
            'compare', 'difference', 'between', 'vs', 'versus', 'khác nhau',
            'so với', 'so sánh', 'giống', 'different', 'same', 'each'
        ]

        # ⭐ NEW: Keywords that indicate a NEW SEARCH across meetings (not follow-up)
        search_keywords = [
            'meeting nào', 'cuộc họp nào', 'which meeting', 'what meeting',
            'đề cập', 'mentioned', 'mention', 'nói về', 'talk about',
            'liên quan', 'related', 'about', 'contain', 'có không'
        ]

        question_lower = question.lower()

        # Extract potential person names (simple heuristic: capitalized words)
        # ⭐ IMPROVED: Exclude common technical terms (not people names)
        exclude_technical_terms = [
            'database', 'api', 'frontend', 'backend', 'feature', 'test', 'system',
            'search', 'authentication', 'server', 'client', 'security'
        ]
        name_pattern = r'\b([A-Z][a-zàáảãạâầấẩẫậăằắẳẵặèéẻẽẹêềếểễệìíỉĩịòóỏõọôồốổỗộơờớởỡợùúủũụưừứửữựỳýỷỹỵđ]+)\b'
        potential_names = [
            n for n in re.findall(name_pattern, question)
            if n.lower() not in exclude_technical_terms
        ]

        # Count keyword matches for each intention type
        scores = {
            "person_focused": sum(1 for kw in person_keywords if kw in question_lower),
            "task_focused": sum(1 for kw in task_keywords if kw in question_lower),
            "decision_focused": sum(1 for kw in decision_keywords if kw in question_lower),
            "time_focused": sum(1 for kw in time_keywords if kw in question_lower),
            "participant_focused": sum(1 for kw in participant_keywords if kw in question_lower),
            "comparison_focused": sum(1 for kw in comparison_keywords if kw in question_lower),
            "topic_focused": 0  # Default fallback
        }

        # ⭐ NEW: Detect if this is a SEARCH query vs FOLLOW-UP question
        search_indicator_score = sum(1 for kw in search_keywords if kw in question_lower)
        is_followup_question = search_indicator_score == 0  # No search keywords = follow-up

        # Determine primary intention
        max_score = max(scores.values())
        primary_intention = max([k for k, v in scores.items() if v == max_score])

        # Calculate confidence (0-1)
        if max_score == 0:
            confidence = 0.3  # Low confidence for generic queries
            primary_intention = "topic_focused"
        else:
            # Confidence = (max_score - second_max_score) / (max_score + 1)
            all_scores = sorted(scores.values(), reverse=True)
            confidence = min(1.0, (all_scores[0] - all_scores[1]) / (all_scores[0] + 1)) if len(all_scores) > 1 else 0.8

        # Determine what metadata to filter by
        should_filter_metadata = {
            "by_participants": primary_intention in ["person_focused", "participant_focused", "comparison_focused"],
            "by_actions": primary_intention in ["task_focused", "person_focused"],
            "by_decisions": primary_intention == "decision_focused",
            "by_duration": primary_intention == "time_focused",
            "by_topics": primary_intention == "topic_focused"
        }

        # Extract entities
        extracted_entities = {
            "people": potential_names, 
            "keywords": [],
            "time_keywords": [kw for kw in time_keywords if kw in question_lower],
            "comparison_keywords": [kw for kw in comparison_keywords if kw in question_lower],
            "search_indicators": [kw for kw in search_keywords if kw in question_lower]  # ⭐ NEW
        }

        # Extract action-related keywords
        if should_filter_metadata["by_actions"]:
            extracted_entities["keywords"] = [kw for kw in task_keywords if kw in question_lower]

        # Build reasoning
        reasoning = f"Query detected as {primary_intention} (confidence: {confidence:.2f}). "
        if is_followup_question:
            reasoning += "⭐ FOLLOW-UP question (about same meeting). "
        else:
            reasoning += f"⭐ NEW SEARCH query (search across meetings). Found {len(extracted_entities['search_indicators'])} search keywords. "

        if potential_names:
            reasoning += f"Valid people: {', '.join(potential_names[:3])}. "
        if extracted_entities["time_keywords"]:
            reasoning += f"Time keywords found. "
        if extracted_entities["comparison_keywords"]:
            reasoning += f"Comparison query. "

        result = {
            "intention_type": primary_intention,
            "confidence": confidence,
            "is_followup_question": is_followup_question,  # ⭐ NEW
            "extracted_entities": extracted_entities,
            "should_filter_metadata": should_filter_metadata,
            "reasoning": reasoning.strip()
        }

        logger.info(f"🔍 Query Intention: {result['intention_type']} | Follow-up: {result['is_followup_question']}")
        logger.info(f"   People: {potential_names} | Search keywords: {extracted_entities['search_indicators']}")
        logger.info(f"   Reasoning: {result['reasoning']}")

        return result

    except Exception as e:
        logger.error(f"Error in query intention classification: {e}")
        # Return safe default
        return {
            "intention_type": "topic_focused",
            "confidence": 0.0,
            "is_followup_question": False,  # ⭐ NEW
            "extracted_entities": {"people": [], "keywords": [], "time_keywords": [], "comparison_keywords": [], "search_indicators": []},
            "should_filter_metadata": {"by_participants": False, "by_actions": False, "by_decisions": False, "by_duration": False, "by_topics": True},
            "reasoning": "Failed to classify intention, defaulting to topic-focused"
        }

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

        # Detect language for appropriate prompting
        is_vietnamese = detect_language(text) == "vi"

        if is_vietnamese:
            prompt = f"""
Bạn là trợ lý tóm tắt cuộc họp chuyên nghiệp. Hãy phân tích biên bản cuộc họp sau và tạo bản tóm tắt CHI TIẾT theo cấu trúc sau:

**QUAN TRỌNG: Tập trung vào 3 yếu tố chính:**
1. THỜI GIAN: Thời lượng cuộc họp, thời gian bắt đầu/kết thúc (nếu có)
2. NGƯỜI THAM GIA: Danh sách đầy đủ người tham gia với vai trò/chức danh của họ
3. NHIỆM VỤ CỤ THỂ: Ai phụ trách làm gì, deadline (nếu có)

**CẤU TRÚC TÓM TẮT:**

## 1. Thông Tin Cuộc Họp
- Thời gian: [Ghi rõ thời gian bắt đầu - kết thúc, hoặc thời lượng cuộc họp]
- Người tham gia: [Liệt kê TẤT CẢ người tham gia với vai trò, ví dụ: "Dev A (Developer), PM Nam (Project Manager)"]

## 2. Nội Dung Chính
[Tóm tắt các nội dung thảo luận quan trọng, 3-5 điểm chính]

## 3. Phân Công Công Việc
[Liệt kê CHI TIẾT ai làm gì, theo format:]
- **[Tên người]** ([Vai trò]): [Nhiệm vụ cụ thể] - Deadline: [nếu có]
- **[Tên người]** ([Vai trò]): [Nhiệm vụ cụ thể] - Deadline: [nếu có]

**LƯU Ý QUAN TRỌNG:**
- Phải ghi CHÍNH XÁC tên người và vai trò như trong biên bản
- KHÔNG được nhầm lẫn giữa các người (ví dụ: Dev A ≠ Dev B)
- Mỗi nhiệm vụ phải ghi rõ ai chịu trách nhiệm
- Trích xuất thời gian/deadline nếu có đề cập
- Sử dụng ngôn ngữ tiếng Việt tự nhiên, rõ ràng

Biên bản cuộc họp:
{text}
"""
        else:
            prompt = f"""
You are a professional meeting summarizer. Analyze the following meeting transcript and create a DETAILED summary with this structure:

**FOCUS ON 3 KEY ELEMENTS:**
1. TIME: Meeting duration, start/end time (if available)
2. PARTICIPANTS: Complete list of participants with their roles/titles
3. SPECIFIC TASKS: Who is responsible for what, with deadlines (if any)

**SUMMARY STRUCTURE:**

## 1. Meeting Information
- Time: [Note start - end time, or meeting duration]
- Participants: [List ALL participants with roles, e.g., "Dev A (Developer), PM John (Project Manager)"]

## 2. Key Discussion Points
[Summarize important discussion topics, 3-5 main points]

## 3. Task Assignments
[List DETAILED assignments using this format:]
- **[Person name]** ([Role]): [Specific task] - Deadline: [if available]
- **[Person name]** ([Role]): [Specific task] - Deadline: [if available]

**IMPORTANT NOTES:**
- Must record names and roles EXACTLY as in the transcript
- DO NOT confuse between people (e.g., Dev A ≠ Dev B)
- Each task must clearly state who is responsible
- Extract time/deadline information if mentioned
- Use clear, natural language

Meeting transcript:
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
    """Enhanced chatbot endpoint with hybrid search, re-ranking, query expansion, context truncation, and validation"""
    try:
        if not client:
            return jsonify({"error": "AI service unavailable"}), 503

        data = request.json
        question = data.get("question", "").strip()
        if not question:
            return jsonify({"error": "No question provided"}), 400

        chat_history = session.get("chat_history", [])
        current_meeting_context = session.get("current_meeting_context", None)  # Track focused meeting
        discussed_meetings = session.get("discussed_meetings", [])  # Track ALL discussed meetings
        context_was_just_updated = session.get("context_was_just_updated", False)  # ⭐ NEW: Track if context was updated from PREVIOUS query

        # ⭐ DEBUG: Log current session context
        logger.info(f"🔍 SESSION STATE at start of Q/A:")
        logger.info(f"   - current_meeting_context: {current_meeting_context}")
        logger.info(f"   - context_was_just_updated: {context_was_just_updated}")
        logger.info(f"   - discussed_meetings count: {len(discussed_meetings)}")

        # --- STEP 0: Extract conversation context ---
        # Detect if user is asking about MULTIPLE meetings (each/all/both)
        multi_meeting_keywords = ['mỗi cuộc họp', 'từng cuộc họp', 'các cuộc họp', 'cả hai cuộc họp',
                                  'each meeting', 'all meetings', 'both meetings', 'những cuộc họp']
        is_multi_meeting_query = any(keyword in question.lower() for keyword in multi_meeting_keywords)

        # Build conversation context
        conversation_context = ""
        if is_multi_meeting_query and len(discussed_meetings) > 1:
            # User is asking about ALL discussed meetings
            meeting_list = ", ".join([f"{m['date']} ({m['title']})" for m in discussed_meetings])
            conversation_context = f"\n\nIMPORTANT CONTEXT: The user has discussed MULTIPLE meetings in this conversation: {meeting_list}. The current question asks about 'each/all' meetings, so it refers to ALL of these meetings, not just the most recent one."
        elif current_meeting_context:
            # User is asking about the most recent meeting
            conversation_context = f"\n\nIMPORTANT CONTEXT: The user was just asking about the meeting on {current_meeting_context['date']} (titled: {current_meeting_context.get('title', 'Unknown')}). If the current question is a follow-up (e.g., asking about someone's tasks, asking 'what about...'), it likely refers to THIS SAME MEETING."

        # --- STEP 1: Classify question ---
        logger.info(f"📥 Received question: '{question}'")
        logger.info(f"📦 Current session context: {session.get('current_meeting_context', {})}")

        # ⭐ SPECIAL HANDLING: Detect general/statistics questions that shouldn't use context filter
        general_keywords = [
            'bao nhiêu', 'how many', 'tất cả', 'all', 'tổng', 'total',
            'danh sách', 'list', 'các cuộc họp', 'meetings', 'tất cả các cuộc họp'
        ]
        is_general_question = any(kw in question.lower() for kw in general_keywords)
        logger.info(f"🔎 Is general/statistics question: {is_general_question}")

        now = datetime.now()
        year = now.year
        month = now.month
        day = now.day

        function_spec = {
            "name": "classify_question",
            "description": "Determine whether the question is about a date or a topic",
            "parameters": {
                "type": "object",
                "properties": {
                    "type": {"type": "string", "enum": ["date", "topic", "specific"]},
                    "date": {"type": "string", "description": f"The date in YYYY-MM-DD format. IMPORTANT: If year is not specified, always use {year} (current year). If month is not specified, use {month} (current month). Examples: '27-10' -> '{year}-10-27', 'October 15' -> '{year}-10-15', 'yesterday' -> calculate based on today ({year}-{month:02d}-{day:02d})."}
                },
                "required": ["type"]
            }
        }

        response = client.chat.completions.create(
            model="gpt-4o-mini",
            messages=[
                {"role": "system", "content": f"You are a classifier for user questions about meetings. Today's date is {year}-{month:02d}-{day:02d}. When users mention dates without years, ALWAYS assume they mean the current year ({year}).{conversation_context}"},
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

        # Post-process: Ensure date uses current year if it seems to be using an old year
        if classification.get("date"):
            parsed_date = classification["date"]
            try:
                # Parse the date
                date_obj = datetime.strptime(parsed_date, "%Y-%m-%d")
                # If year is before 2024 or after current year + 1, assume it should be current year
                if date_obj.year < 2024 or date_obj.year > year + 1:
                    logger.warning(f"⚠️ Detected unusual year {date_obj.year} in date '{parsed_date}'. Correcting to current year {year}.")
                    classification["date"] = f"{year}-{date_obj.month:02d}-{date_obj.day:02d}"
            except ValueError:
                logger.warning(f"⚠️ Could not parse date '{parsed_date}' for year validation")

        logger.info(f"🧩 Classified as: {classification}")
        logger.info(f"❓ Original question: '{question}'")

        # --- STEP 1.5: Classify query intention for targeted result filtering ---
        query_intention = classify_query_intention(
            question=question,
            conversation_context=conversation_context,
            chat_history=chat_history
        )
        logger.info(f"🎯 Query Intention Classification: {query_intention['intention_type']}")
        logger.info(f"   Entities: People={query_intention['extracted_entities']['people']}, Keywords={query_intention['extracted_entities']['keywords']}")

        # --- STEP 2: Prepare search filter ---
        date_filter = classification.get("date") if classification["type"] == "date" else None
        multi_date_filter = None  # For filtering multiple meetings

        # 🔥 MULTI-MEETING ENHANCEMENT: If user asks about "each/all" meetings, search ALL discussed meetings
        is_context_query = False
        is_multi_meeting_search = False
        if is_multi_meeting_query and len(discussed_meetings) > 1 and date_filter is None:
            # User wants info across ALL discussed meetings
            multi_date_filter = [m['date'] for m in discussed_meetings]
            is_context_query = True
            is_multi_meeting_search = True
            logger.info(f"🔥 Multi-meeting query detected: Searching across {len(multi_date_filter)} meetings: {multi_date_filter}")

        # ⭐ IMPROVED CONTEXT-AWARE: Only apply date filter for TRUE follow-up questions, NOT for search queries
        # A follow-up question asks about the SAME meeting (e.g., "có những ai", "làm gì")
        # A search query asks across meetings (e.g., "meeting nào đề cập X", "cuộc họp nào nói về Y")
        # ⭐ CRITICAL FIX: Always use CURRENT context for follow-ups (whether it was just updated or not)
        # ⭐ NEW: Skip context for general/statistics questions (e.g., "Bao nhiêu cuộc họp", "Danh sách tất cả")
        elif (classification["type"] == "topic" and
              current_meeting_context and
              date_filter is None and
              query_intention.get("is_followup_question", False) and
              not is_general_question):  # ⭐ NEW: Don't use context for general questions
            # This is a FOLLOW-UP question about the CURRENT meeting
            # Always use the current_meeting_context, regardless of when it was last updated
            date_filter = current_meeting_context['date']
            is_context_query = True
            logger.info(f"💡 Context-aware query (FOLLOW-UP): Using current meeting date '{date_filter}' for follow-up question")
            logger.info(f"   Context meeting: {current_meeting_context.get('title', 'Unknown')} ({current_meeting_context.get('date')})")
            logger.info(f"   Context was last updated in previous query: {context_was_just_updated}")
        elif is_general_question:
            # ⭐ NEW: General/statistics question - search ALL meetings, ignore context
            logger.info(f"📊 General/statistics question detected: Searching across ALL meetings (no context filter)")
            is_context_query = False
            date_filter = None
        elif classification["type"] == "topic" and date_filter is None and not query_intention.get("is_followup_question", False):
            # This is a NEW SEARCH query - search across ALL meetings, not just the current one
            logger.info(f"🔍 NEW SEARCH query detected: Searching across ALL meetings (not limited to '{current_meeting_context['date'] if current_meeting_context else 'N/A'}')")

        # ⭐ DEBUG: Log the final decision about date_filter
        logger.info(f"🔎 FINAL STATE before search:")
        logger.info(f"   - classification.type={classification.get('type')}")
        logger.info(f"   - current_meeting_context={current_meeting_context}")
        logger.info(f"   - is_followup_question={query_intention.get('is_followup_question', False)}")
        logger.info(f"   - date_filter={date_filter}")
        logger.info(f"   - is_context_query={is_context_query}")

        # Debug: Show available dates in database
        try:
            all_docs = meeting_collection.get()
            available_dates = set()
            if all_docs and 'metadatas' in all_docs:
                for metadata in all_docs['metadatas']:
                    if metadata and 'date' in metadata:
                        available_dates.add(metadata['date'])
            logger.info(f"📅 Available dates in database: {sorted(available_dates)}")
            logger.info(f"🔍 Date filter applied: {date_filter if date_filter else multi_date_filter}")
        except Exception as e:
            logger.warning(f"⚠️ Could not retrieve available dates: {e}")

        # --- STEP 3: Semantic search (ChromaDB vector search with date filter) ---
        # Support both single date and multiple dates
        if multi_date_filter:
            where_filter = {"date": {"$in": multi_date_filter}}  # Match any of the discussed meetings
        elif date_filter:
            where_filter = {"date": date_filter}  # Match single meeting
        else:
            where_filter = None  # No filter (search all)

        logger.info(f"📊 Search filters: date_filter={date_filter}, multi_date_filter={multi_date_filter}, where_filter={where_filter}")

        # ⭐ IMPORTANT: For follow-up questions, track if we're using a date filter
        is_using_context_filter = date_filter and is_context_query

        try:
            semantic_results = meeting_collection.query(
                query_texts=[question],
                n_results=10,
                where=where_filter
            )

            # Convert to standard format
            search_results = []
            if semantic_results and semantic_results['documents'] and semantic_results['documents'][0]:
                for i in range(len(semantic_results['documents'][0])):
                    distance = semantic_results['distances'][0][i] if 'distances' in semantic_results else 0
                    similarity = 1 - distance

                    # --- STEP 3.5: Intention-aware result filtering ---
                    meta = semantic_results['metadatas'][0][i]
                    should_include = True
                    filter_reason = ""

                    # For date queries: accept ALL results since ChromaDB already filtered by date
                    if classification["type"] == "date" or is_context_query:
                        should_include = True
                        filter_reason = "date/context filter"
                    # Apply intention-based metadata filtering
                    else:
                        # Check metadata relevance based on query intention
                        if query_intention["should_filter_metadata"]["by_actions"]:
                            # For action/task queries, prioritize results with action info
                            has_actions = meta.get('has_actions', False)
                            action_count = meta.get('action_count', 0)
                            if action_count == 0:
                                logger.info(f"   Result {i+1}: distance={distance:.4f} (has no actions, might be less relevant)")

                        if query_intention["should_filter_metadata"]["by_duration"]:
                            # For time queries, check if duration info is available
                            duration = meta.get('duration_minutes', 0)
                            if duration == 0:
                                logger.info(f"   Result {i+1}: distance={distance:.4f} (has no duration info)")

                        if query_intention["should_filter_metadata"]["by_decisions"]:
                            # For decision queries, prioritize meetings with decision info
                            has_decisions = meta.get('has_decisions', False)
                            if not has_decisions:
                                logger.info(f"   Result {i+1}: distance={distance:.4f} (might not have decisions)")

                        # Apply similarity threshold based on intention and confidence
                        if query_intention["intention_type"] == "topic_focused":
                            # Topic queries: stricter similarity threshold
                            if distance > 1.5:
                                should_include = False
                                filter_reason = f"low similarity for topic query (distance={distance:.4f})"
                        elif query_intention["intention_type"] in ["person_focused", "task_focused"]:
                            # Person/task queries: moderate threshold
                            if distance > 1.3:
                                should_include = False
                                filter_reason = f"low similarity for {query_intention['intention_type']} query"
                        else:
                            # Other intentions: more lenient
                            if distance > 1.8:
                                should_include = False
                                filter_reason = f"low similarity for {query_intention['intention_type']} query"

                    if should_include:
                        search_results.append({
                            'id': semantic_results['ids'][0][i],
                            'summary': semantic_results['documents'][0][i],
                            'metadata': meta,
                            'distance': distance,
                            'similarity': similarity,
                            'intention_matched': True
                        })
                        logger.info(f"   Result {i+1}: distance={distance:.4f} (accepted - {filter_reason or 'matches intention'})")
                    else:
                        logger.info(f"   Result {i+1}: distance={distance:.4f} (filtered out - {filter_reason})")

            logger.info(f"🔍 Semantic search returned {len(search_results)} results (after intention-based filtering)")
            logger.info(f"   Raw semantic_results count: {len(semantic_results['documents'][0]) if semantic_results and semantic_results['documents'] and semantic_results['documents'][0] else 0}")

            # ⭐ CRITICAL FIX: If this is a follow-up question with context, FORCE results to stay within context meeting
            # BUT: Don't filter if it's a general/statistics question (is_general_question) or a new search
            if (query_intention.get("is_followup_question", False) and
                current_meeting_context and
                len(search_results) > 0 and
                not is_general_question):  # ⭐ NEW: Don't filter general questions
                context_date = current_meeting_context['date']
                results_in_context = [r for r in search_results if r['metadata'].get('date') == context_date]

                if results_in_context:
                    logger.info(f"⭐ FOLLOW-UP: Filtering results to context meeting ({context_date})")
                    logger.info(f"   Found {len(results_in_context)} results in context meeting (from {len(search_results)} total)")
                    search_results = results_in_context
                else:
                    logger.warning(f"⚠️ FOLLOW-UP: No results found in context meeting ({context_date})")
                    logger.warning(f"   Context meeting: {current_meeting_context.get('title')} ({context_date})")
                    logger.warning(f"   Keeping broader search results from {[r['metadata'].get('date') for r in search_results]}")
                    logger.warning(f"   Note: If you want to search across all meetings, ask a NEW SEARCH question instead")
            elif is_general_question:
                logger.info(f"📊 GENERAL QUESTION: NOT filtering results by context - using all {len(search_results)} results")

            if len(search_results) > 0:
                logger.info(f"📊 Top results (after context filtering):")
                for i, result in enumerate(search_results):
                    logger.info(f"   {i+1}. Date: {result.get('metadata', {}).get('date', 'N/A')}, Title: {result.get('metadata', {}).get('title', 'N/A')[:50]}..., Distance: {result.get('distance', 'N/A'):.4f}")
            else:
                logger.warning(f"⚠️ Semantic search returned 0 results. This might indicate:")

                # Check if date filter was applied and if date exists
                if date_filter:
                    if date_filter in available_dates:
                        logger.warning(f"   ✓ Date '{date_filter}' exists in database")
                        logger.warning(f"   ✗ But all results filtered out due to low similarity (distance > 0.5)")
                        logger.warning(f"   → Try asking about specific topics from that meeting")
                    else:
                        logger.warning(f"   ✗ Date mismatch: Looking for '{date_filter}' but available dates are: {sorted(available_dates)}")
                        logger.warning(f"   → Please check the date format or ask about a different date")
                else:
                    logger.warning(f"   - No semantic similarity found for the query")
                    logger.warning(f"   - Try rephrasing your question or being more specific")

        except Exception as e:
            logger.error(f"❌ Error in semantic search: {e}")
            search_results = []

        # --- STEP 4: Build context with rich metadata ---
        context = ""
        meeting_details = []
        total_context_chars = 0

        if search_results:
            context = "📋 Relevant Meeting Information:\n\n"

            for idx, result in enumerate(search_results):
                meta = result["metadata"]
                summary = result['summary']

                # Calculate relevance score
                if 'rerank_score' in result:
                    relevance = round(result['rerank_score'] * 100, 1)
                elif 'hybrid_score' in result:
                    relevance = round(result['hybrid_score'] * 100, 1)
                else:
                    relevance = round((1 - result.get('distance', 0)) * 100, 1) if result.get('distance') is not None else 100

                # Store meeting details for reference
                meeting_info = {
                    "index": idx + 1,
                    "title": meta['title'],
                    "date": meta['date'],
                    "filename": meta.get('filename', ''),
                    "id": result['id'],
                    "relevance": relevance,
                    "meeting_type": meta.get('meeting_type', 'general'),
                    "priority": meta.get('priority', 'normal'),
                    "has_decisions": meta.get('has_decisions', False),
                    "summary": summary
                }
                meeting_details.append(meeting_info)

                # ⭐ Enhanced context with NEW metadata structure
                meeting_context = f"{'='*80}\n"
                meeting_context += f"[MEETING {idx + 1}]\n"
                meeting_context += f"{'='*80}\n"
                meeting_context += f"📅 Date: {meta['date']}\n"
                meeting_context += f"📌 Title: {meta['title']}\n"
                meeting_context += f"🏷️  Type: {meta.get('meeting_type', 'general')}\n"

                # ⭐ NEW: Time information (improved)
                duration_min = meta.get('duration_minutes', 0)
                duration_source = meta.get('duration_source', 'unknown')
                start_time = meta.get('start_time', '')
                end_time = meta.get('end_time', '')

                if start_time and end_time:
                    meeting_context += f"⏱️  Duration: {duration_min} min ({start_time} - {end_time}) [{duration_source}]\n"
                elif duration_min > 0:
                    meeting_context += f"⏱️  Duration: {duration_min} min [{duration_source}]\n"

                # ⭐ NEW: Participants with roles
                if meta.get('participants'):
                    meeting_context += f"👥 Participants ({meta.get('participant_count', 0)}): {meta.get('participants')}\n"

                # ⭐ NEW: Participant roles (if available)
                if meta.get('participant_roles'):
                    try:
                        roles_dict = json.loads(meta.get('participant_roles', '{}'))
                        if roles_dict:
                            meeting_context += f"   Roles: "
                            role_strs = [f"{name} ({role})" for name, role in roles_dict.items()]
                            meeting_context += ", ".join(role_strs) + "\n"
                    except:
                        pass

                # ⭐ NEW: Individual actions
                individual_actions = meta.get('individual_actions', '')
                if individual_actions:
                    meeting_context += f"📝 Individual Actions:\n"
                    for action_str in individual_actions.split(' | '):
                        meeting_context += f"   • {action_str}\n"

                meeting_context += f"🎯 Relevance Score: {relevance}%\n"
                meeting_context += f"\n📄 CONTENT:\n{summary}\n"
                meeting_context += f"{'-'*80}\n\n"

                context += meeting_context
                total_context_chars += len(meeting_context)

        # --- STEP 5: Truncate context if needed ---
        if context:
            try:
                context, context_tokens = truncate_context_intelligently(
                    context=context,
                    max_tokens=6000,
                    model="gpt-4o-mini"
                )
                logger.info(f"📄 Context: {total_context_chars} chars, {context_tokens} tokens")
            except Exception as e:
                logger.warning(f"⚠️ Error truncating context: {e}. Using full context.")
                context_tokens = 0
        else:
            context_tokens = 0
            logger.info(f"📄 No context to truncate (empty search results)")

        # --- STEP 6: Generate answer with metadata-aware prompting (enhanced with intention-based guidance) ---

        # Build intention-specific instructions
        intention_guidance = ""
        if query_intention["intention_type"] == "time_focused":
            intention_guidance = "\n⏱️ **QUERY INTENTION: TIME-FOCUSED**\nLàm rõ về THỜI GIAN: Trích xuất metadata 'duration_minutes', 'start_time', 'end_time', 'duration_source'."
        elif query_intention["intention_type"] == "person_focused":
            intention_guidance = f"\n👤 **QUERY INTENTION: PERSON-FOCUSED**\nHỏi về NGƯỜI: Tập trung vào participant roles và individual actions. Extracted people: {', '.join(query_intention['extracted_entities']['people']) or 'N/A'}"
        elif query_intention["intention_type"] == "task_focused":
            intention_guidance = "\n✅ **QUERY INTENTION: TASK-FOCUSED**\nHỏi về NHIỆM VỤ/HÀNH ĐỘNG: Trích xuất từ 'individual_actions' metadata và 'CONTENT' section. Ưu tiên thông tin từ CONTENT."
        elif query_intention["intention_type"] == "participant_focused":
            intention_guidance = "\n👥 **QUERY INTENTION: PARTICIPANT-FOCUSED**\nHỏi về NGƯỜI THAM GIA: Trích xuất 'participants', 'participant_count', 'participant_roles' metadata."
        elif query_intention["intention_type"] == "decision_focused":
            intention_guidance = "\n🎯 **QUERY INTENTION: DECISION-FOCUSED**\nHỏi về QUYẾT ĐỊNH: Tập trung vào phần 'CONTENT' để tìm các quyết định, phê duyệt, hoặc kết luận."
        elif query_intention["intention_type"] == "comparison_focused":
            intention_guidance = f"\n🔄 **QUERY INTENTION: COMPARISON-FOCUSED**\nSo sánh GIỮA CÁC CUỘC HỌP: Cân nhắc kỹ lưỡng từng meeting context, ghi rõ sự khác nhau và giống nhau."
        else:
            intention_guidance = "\n📋 **QUERY INTENTION: TOPIC-FOCUSED**\nHỏi về CHỦ ĐỀ: Tìm thông tin liên quan đến các chủ đề được thảo luận."

        system_prompt = f"""Bạn là trợ lý thông minh chuyên phân tích và tổng hợp thông tin từ các cuộc họp.

📋 HƯỚNG DẪN TRẢ LỜI:

0. **PHÂN LOẠI INTENT CỦA CÂUHỎI (CẢI TIẾN MỚI):**{intention_guidance}
   - Confidence level: {query_intention['confidence']:.2f}/1.0
   - Reasoning: {query_intention['reasoning']}

   {'⭐ SPECIAL INSTRUCTION: Đây là một câu hỏi thống kê/tổng quan - hãy trả lời dựa trên TẤT CẢ các cuộc họp trong context, không chỉ một cuộc họp cụ thể.' if is_general_question else ''}

1. **Sử dụng metadata mới (CẢI TIẾN):**

   🕐 **Thông tin thời gian:**
   - Duration: Thời lượng cuộc họp (phút)
   - Start/End Time: Thời gian bắt đầu/kết thúc (nếu có)
   - Duration Source: Nguồn thời gian (explicit_mention=rõ ràng, time_range=từ khoảng thời gian, estimated=ước tính)

   👥 **Thông tin người tham gia:**
   - Participants: Danh sách người tham gia
   - Participant Roles: Vai trò của từng người (JSON format)
   - Participant Count: Số lượng người tham gia

   📝 **Nhiệm vụ cá nhân:**
   - Individual Actions: Nhiệm vụ cụ thể của từng người
   - Định dạng: "Người: Nhiệm vụ (deadline: ngày)"

2. **Cấu trúc câu trả lời theo loại câu hỏi (dựa trên INTENT):**

   ⏱️ **Khi hỏi về THỜI GIAN:**
   - Trả lời thời lượng cuộc họp từ metadata "duration_minutes"
   - Nếu có start_time/end_time, đề cập luôn
   - Cho biết nguồn thông tin (chính xác hay ước tính)
   - Ví dụ: "Cuộc họp kéo dài 60 phút (từ 9:00 đến 10:00)"

   👤 **Khi hỏi về NGƯỜI/NHÂN VẬT:**
   - Liệt kê từ metadata "participants" và "participant_roles"
   - Ghi rõ vai trò của từng người
   - Liệt kê các tasks được gán cho từng người
   - Ví dụ: "Có 4 người tham gia: Dev A (Developer), PM Nam (Project Manager), Tester B (Tester), Designer C (Designer)"

   ✅ **Khi hỏi về HÀNH ĐỘNG/NHIỆM VỤ CỦA NGƯỜI CỤ THỂ:**
   - **ƯU TIÊN TUYỆT ĐỐI:** Đọc từ phần "📄 CONTENT:" (summary text) TRƯỚC
   - Chỉ tham khảo metadata "individual_actions" để bổ sung
   - Nếu có mâu thuẫn giữa CONTENT và metadata → TIN CONTENT
   - Ghi RÕ ai làm gì, deadline (nếu có)
   - PHẢI chính xác 100% - KHÔNG nhầm lẫn người
   - Ví dụ:
     • Dev A: Hoàn thiện API authentication (deadline: 2024-12-01)
     • Tester B: Viết test cases cho module login

   👥 **Khi hỏi về NGƯỜI THAM GIA:**
   - Trích dẫn trực tiếp từ metadata "participants" field
   - Ghi rõ số lượng và vai trò từ "participant_count" và "participant_roles"
   - Ví dụ: "Cuộc họp có 5 người tham gia: Dev A (Developer), Dev B (Developer), PM Nam (Project Manager), Tester Linh (Tester), Designer Hạnh (Designer)"

   🎯 **Khi hỏi về QUYẾT ĐỊNH:**
   - Tìm từ phần "📄 CONTENT:" các quyết định, kết luận, phê duyệt
   - Liệt kê rõ ràng từng quyết định được đưa ra
   - Ví dụ: "Các quyết định chính: (1) Phê duyệt version 1.0 của feature X, (2) Hoãn release date thêm 2 tuần"

3. **Quy tắc quan trọng - PHẢI TUÂN THỦ NGHIÊM NGẶT:**
   - ⚠️ **QUY TẮC SỐ 1:** Khi trả lời về nhiệm vụ của người cụ thể, ĐỌC TRỰC TIẾP từ phần "📄 CONTENT:"
   - CHỈ sử dụng thông tin có CHÍNH XÁC trong context
   - KHÔNG được bịa đặt, suy luận, hoặc thêm thắt thông tin
   - KHÔNG được nhầm lẫn người và vai trò (ví dụ: Dev A ≠ Dev B, Dev A ≠ PM Nam)
   - Khi trích dẫn ai làm gì, PHẢI chính xác 100% từ CONTENT section
   - Nếu metadata "individual_actions" khác với CONTENT → TIN CONTENT (vì CONTENT chính xác hơn)
   - Nếu không chắc chắn hoặc không có thông tin, hãy nói thẳng "Tôi không tìm thấy thông tin về..."

4. **Ví dụ câu trả lời tốt:**

   ❌ SAI: "Dev B phụ trách xây dựng database" (khi context nói Dev A làm)
   ✅ ĐÚNG: "Dev A phụ trách API và database, Dev B phụ trách frontend"

   ❌ SAI: "Cuộc họp khoảng 1 tiếng" (khi có thông tin chính xác)
   ✅ ĐÚNG: "Cuộc họp kéo dài 65 phút (từ 9:00 đến 10:05)"

5. **Sử dụng Relevance Score:**
   - Meetings có Relevance Score cao hơn (>70%) thường có thông tin chính xác hơn
   - Nếu score thấp (<50%), hãy thận trọng khi đưa ra kết luận

📚 CONTEXT:
{context if context.strip() else "⚠️ Không tìm thấy dữ liệu cuộc họp cho câu hỏi này. Hãy nói rõ rằng bạn không thể trả lời."}

📤 ĐỊNH DẠNG KẾT QUẢ TRẢ VỀ (LINH HOẠT):

**LƯU Ý:** Trả lời một câu trả lời tự nhiên, rõ ràng, ngắn gọn.

Nếu bạn muốn, bạn có thể sử dụng JSON format sau để giúp tổ chức thông tin:
{{
  "answer": "Câu trả lời hoàn chỉnh, ngắn gọn, đúng ngữ cảnh, tuân theo các quy tắc trên.",
  "titleMeetings": ["Tên cuộc họp 1", "Tên cuộc họp 2"]
}}

**TUỲ CHỌN - Bạn có thể:**
- Trả lời bằng JSON format (nếu có thể)
- Hoặc trả lời bằng plain text tự nhiên

**Ưu tiên:**
1. **Câu trả lời chính xác, hữu ích** > Định dạng cứng nhắc
2. Nếu là plain text: Câu trả lời nên rõ ràng, chi tiết, theo ngữ cảnh
3. Ghi rõ tên cuộc họp nếu có thể (để hỗ trợ tìm kiếm)

**Ví dụ:**
✅ ĐÚNG: "Có 5 người tham gia: PM (Project Manager), Dev A (Developer A - Backend), Dev B (Developer B - Frontend), Designer, Tester."
✅ ĐÚNG: {{"answer": "Có 5 người tham gia...", "titleMeetings": ["Meeting Name"]}}
❌ KHÔNG cần: Code block không cần thiết, plain text tốt hơn
"""

        messages = [{"role": "system", "content": system_prompt}]
        messages.extend(chat_history[-10:])
        messages.append({"role": "user", "content": question})

        # --- STEP 6.4: Generate answer (FLEXIBLE MODE - no strict JSON requirement) ---
        # Removed strict JSON mode to support Vietnamese text better
        # We'll parse the response flexibly instead
        answer_response = client.chat.completions.create(
            model="gpt-4o-mini",
            messages=messages,
            temperature=0,  # Zero temperature for maximum accuracy and no hallucinations
            max_tokens=1500
            # Note: Removed response_format={"type": "json_object"} for better Vietnamese support
        )

        # --- STEP 6.5: Parse and validate response with FLEXIBLE JSON extraction ---
        response_content = answer_response.choices[0].message.content

        # Debug logging
        logger.info(f"📨 Raw API Response length: {len(response_content) if response_content else 0}")
        if response_content:
            logger.info(f"📨 First 300 chars: {response_content[:300]}")

        # Parse JSON with intelligent fallback strategy
        result = None

        if not response_content or response_content.strip() == "":
            logger.error("❌ API returned empty response")
            result = {
                "answer": "Xin lỗi, tôi không thể xử lý câu hỏi này. Vui lòng thử lại.",
                "titleMeetings": []
            }
        else:
            # --- Try multiple JSON extraction strategies ---

            # Strategy 1: Direct JSON parsing
            try:
                result = json.loads(response_content)
                logger.info(f"✅ Strategy 1 SUCCESS: Directly parsed JSON response")
            except json.JSONDecodeError:
                logger.info(f"⚠️ Strategy 1 FAILED: Direct JSON parsing")

                # Strategy 2: Extract JSON from code blocks (```json...```)
                json_from_codeblock = re.search(r'```(?:json)?\s*(\{.*?\})\s*```', response_content, re.DOTALL)
                if json_from_codeblock:
                    try:
                        result = json.loads(json_from_codeblock.group(1))
                        logger.info(f"✅ Strategy 2 SUCCESS: Extracted JSON from code block")
                    except json.JSONDecodeError:
                        logger.info(f"⚠️ Strategy 2 FAILED: Code block extraction")

                # Strategy 3: Extract JSON with balanced braces
                if not result:
                    json_match = re.search(r'\{[^{}]*(?:\{[^{}]*\}[^{}]*)*\}', response_content, re.DOTALL)
                    if json_match:
                        try:
                            result = json.loads(json_match.group())
                            logger.info(f"✅ Strategy 3 SUCCESS: Extracted JSON with balanced braces")
                        except json.JSONDecodeError:
                            logger.info(f"⚠️ Strategy 3 FAILED: Balanced braces extraction")

                # Strategy 4: Create JSON from plain text response
                if not result:
                    logger.info(f"⚠️ All JSON extraction strategies failed. Using fallback text parsing.")
                    # The response is likely plain text - wrap it in JSON
                    # Try to extract meeting titles from the response
                    answer_text = response_content.strip()

                    # Extract potential meeting titles (usually in quotes or after specific patterns)
                    title_matches = re.findall(r'["\']([^"\']*(?:Meeting|Cuộc họp|họp)[^"\']*)["\']', answer_text, re.IGNORECASE)

                    # Also check meeting_details for any that might be in the answer
                    titles_in_answer = []
                    for detail in meeting_details:
                        if detail['title'] in answer_text:
                            titles_in_answer.append(detail['title'])

                    result = {
                        "answer": answer_text,
                        "titleMeetings": titles_in_answer if titles_in_answer else title_matches[:3]
                    }
                    logger.info(f"✅ Strategy 4 SUCCESS: Created JSON from plain text response")
                    logger.info(f"   Answer length: {len(answer_text)} chars")
                    logger.info(f"   Extracted {len(result['titleMeetings'])} meeting titles")

        # ⭐ FIXED: Removed print statement that caused UnicodeEncodeError with Vietnamese text
        # print("result: " + str(result))
        raw_answer = result.get("answer", "Xin lỗi, tôi không chắc cách trả lời câu hỏi đó.")
        # --- STEP 7: Validate answer grounding (hallucination detection) ---
        validation = validate_answer_grounding(
            answer=raw_answer,
            context=context,
            client=client
        )

        logger.info(f"✅ Answer validation: {validation}")

        # Add disclaimer if needed
        formatted_answer = add_validation_disclaimer(raw_answer, validation)

        # --- STEP 8: Update chat history & meeting context ---
        chat_history.append({"role": "user", "content": question})
        chat_history.append({"role": "assistant", "content": formatted_answer})
        session["chat_history"] = chat_history[-20:]

        # ⭐ IMPROVED CONTEXT TRACKING: Only update context on NEW SEARCHES, not follow-ups
        # If this was a follow-up question with a date filter, DON'T update context
        # because we want to maintain the context across follow-up questions
        if len(search_results) > 0:
            # Store the current focused meeting (the most relevant result)
            first_meeting = search_results[0]['metadata']
            new_context = {
                "date": first_meeting.get('date'),
                "title": first_meeting.get('title', 'Unknown'),
                "id": search_results[0]['id']
            }

            # Check if this is a NEW meeting (different from current context)
            old_context = session.get("current_meeting_context", {})
            is_new_meeting = (old_context.get('date') != new_context['date'] or
                             not old_context.get('date'))  # First time or different date

            # ⭐ CRITICAL FIX: Only update context on TRUE NEW SEARCHES, not follow-up questions
            # - Don't update if this was a FOLLOW-UP question (is_followup_question == True)
            # - Do update if this was a NEW SEARCH across meetings (is_followup_question == False)
            # - Multi-meeting searches (is_context_query for multi_date_filter) are OK to update from
            is_followup_question = query_intention.get("is_followup_question", False)
            is_multi_meeting_with_filter = is_multi_meeting_search and multi_date_filter is not None

            should_update_context = (
                (not is_followup_question) or  # Update on new searches
                is_multi_meeting_with_filter    # Update on multi-meeting queries
            )

            # ⭐ DEBUG: Log context update decision
            logger.info(f"📋 Context update decision:")
            logger.info(f"   - is_followup_question={is_followup_question}")
            logger.info(f"   - is_multi_meeting_with_filter={is_multi_meeting_with_filter}")
            logger.info(f"   - should_update_context={should_update_context}")
            logger.info(f"   - Old context: {old_context.get('date', 'None')}")
            logger.info(f"   - New context from search (top result): {new_context['date']}")
            logger.info(f"   - Top result relevance score: {search_results[0].get('distance', 'N/A') if search_results else 'N/A'}")
            if len(search_results) > 1:
                logger.info(f"   - Second result: {search_results[1]['metadata'].get('date')} (relevance: {search_results[1].get('distance', 'N/A')})")

            if should_update_context:
                session["current_meeting_context"] = new_context
                session["context_was_just_updated"] = True  # ⭐ NEW: Mark that context was just updated

                if is_new_meeting:
                    logger.info(f"💾 ⭐ UPDATED meeting context to: {new_context['date']} - {new_context['title']}")
                    if old_context.get('date'):
                        logger.info(f"   (Changed from: {old_context['date']})")
                else:
                    logger.info(f"💾 Context remains: {new_context['date']} - {new_context['title']}")
            else:
                session["context_was_just_updated"] = False  # ⭐ NEW: Mark that context was NOT updated (follow-up)
                logger.info(f"💾 Context PRESERVED: {old_context.get('date', 'None')} (follow-up question, not updating)")
                logger.info(f"   (First result was from {new_context['date']}, but keeping original context)")

            # 🔥 MULTI-MEETING TRACKING: Add ALL found meetings to discussed_meetings list
            if not is_multi_meeting_search:
                # Single meeting query - add this meeting to the list if not already present
                discussed_meetings_updated = discussed_meetings.copy()
                meeting_dates = [m['date'] for m in discussed_meetings_updated]

                if first_meeting.get('date') not in meeting_dates:
                    # New meeting - add to list (keep last 5 meetings)
                    discussed_meetings_updated.append({
                        "date": first_meeting.get('date'),
                        "title": first_meeting.get('title', 'Unknown'),
                        "id": search_results[0]['id']
                    })
                    # Keep only last 5 meetings to avoid too much context
                    session["discussed_meetings"] = discussed_meetings_updated[-5:]
                    logger.info(f"📚 Added to discussed meetings list (now tracking {len(session['discussed_meetings'])} meetings)")
        else:
            # No results found
            if classification["type"] == "topic" and not date_filter and not multi_date_filter:
                # If it was a topic query with no context and no results, clear the context
                session.pop("current_meeting_context", None)
                logger.info(f"🗑️ Cleared meeting context (no results)")

        titleMeetings = result["titleMeetings"] if "titleMeetings" in result else []
        filtered_meetings = [m for m in meeting_details if m["title"] in titleMeetings]
        # ⭐ FIXED: Removed print statement that caused UnicodeEncodeError
        # print("filtered_meetings: " + str(filtered_meetings))

        return jsonify({
            "answer": formatted_answer,
            "classification": classification,
            # ⭐ NEW: Query Intention Classification
            "query_intention": {
                "type": query_intention["intention_type"],
                "confidence": query_intention["confidence"],
                "reasoning": query_intention["reasoning"],
                "extracted_entities": {
                    "people": query_intention["extracted_entities"]["people"],
                    "keywords": query_intention["extracted_entities"]["keywords"]
                },
                "metadata_filters_applied": query_intention["should_filter_metadata"]
            },
            "meetings": filtered_meetings,
            "count": len(search_results),
            "validation": {
                "is_grounded": validation.get("is_grounded", True),
                "confidence": validation.get("confidence", "medium")
            },
            "search_stats": {
                "semantic_results": len(search_results),
                "final": len(search_results),
                "context_tokens": context_tokens,
                "search_type": "semantic_with_intention_filtering"
            },
            "context_used": is_context_query,  # Indicate if we used conversation context
            "multi_meeting_search": is_multi_meeting_search,  # Indicate if searching across multiple meetings
            "current_meeting": session.get("current_meeting_context"),  # Show current focused meeting
            "discussed_meetings": session.get("discussed_meetings", [])  # Show all discussed meetings
        })

    except Exception as e:
        logger.error(f"Error in chatbot: {e}", exc_info=True)
        return jsonify({"error": "Failed to process question"}), 500

@app.route("/clear_session", methods=["POST"])
def clear_session_data():
    """Clear session data (chat history, context, discussed meetings)"""
    try:
        logger.info("🗑️ Clearing session data...")
        session.clear()
        logger.info("✅ Session cleared successfully")
        return jsonify({
            "success": True,
            "message": "Session cleared. Ready for fresh conversation."
        })
    except Exception as e:
        logger.error(f"Error clearing session: {e}")
        return jsonify({"error": "Failed to clear session"}), 500

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

@app.route("/get_all_data", methods=["GET"])
def get_all_data():
    """Get all documents from ChromaDB with full details for data management"""
    try:
        # Get all documents from ChromaDB
        all_docs = meeting_collection.get()

        documents = []
        if all_docs and 'ids' in all_docs:
            for i in range(len(all_docs['ids'])):
                doc = {
                    'id': all_docs['ids'][i],
                    'content': all_docs['documents'][i] if 'documents' in all_docs else '',
                    'metadata': all_docs['metadatas'][i] if 'metadatas' in all_docs else {},
                    'content_length': len(all_docs['documents'][i]) if 'documents' in all_docs else 0,
                    'content_preview': all_docs['documents'][i][:200] + '...' if 'documents' in all_docs and len(all_docs['documents'][i]) > 200 else all_docs['documents'][i] if 'documents' in all_docs else ''
                }
                documents.append(doc)

        logger.info(f"✅ Retrieved {len(documents)} documents from ChromaDB")
        return jsonify({
            "documents": documents,
            "total": len(documents)
        })

    except Exception as e:
        logger.error(f"Error getting all data: {e}")
        return jsonify({"error": "Failed to get data"}), 500

@app.route("/delete_document/<doc_id>", methods=["DELETE"])
def delete_document(doc_id):
    """Delete a specific document from ChromaDB"""
    try:
        # Delete from ChromaDB
        meeting_collection.delete(ids=[doc_id])

        logger.info(f"✅ Deleted document: {doc_id}")
        return jsonify({
            "success": True,
            "message": f"Document {doc_id} deleted successfully"
        })

    except Exception as e:
        logger.error(f"Error deleting document {doc_id}: {e}")
        return jsonify({"error": "Failed to delete document"}), 500

@app.route("/search_meetings", methods=["POST"])
def search_meetings():
    """Search meetings using semantic search with metadata filtering"""
    try:
        data = request.json
        query = data.get("query", "").strip()
        n_results = data.get("n_results", 5)

        # ⭐ NEW: Support metadata filters
        meeting_type = data.get("meeting_type")
        priority = data.get("priority")
        has_decisions = data.get("has_decisions")
        has_action_items = data.get("has_action_items")

        if not query:
            return jsonify({"error": "No search query provided"}), 400

        results = search_meetings_chromadb(
            query=query,
            n_results=n_results,
            meeting_type=meeting_type,
            priority=priority,
            has_decisions=has_decisions,
            has_action_items=has_action_items
        )

        formatted_results = []
        for result in results:
            formatted_results.append({
                "id": result['id'],
                "title": result['metadata']['title'],
                "date": result['metadata']['date'],
                "meeting_type": result['metadata'].get('meeting_type', 'general'),
                "priority": result['metadata'].get('priority', 'normal'),
                "has_decisions": result['metadata'].get('has_decisions', False),
                "action_items_count": result['metadata'].get('action_items_count', 0),
                "summary": result['summary'][:300] + "...",
                "relevance": 1 - result['distance'] if result['distance'] else 1.0
            })

        return jsonify({
            "success": True,
            "results": formatted_results,
            "total": len(formatted_results),
            "filters_applied": {
                "meeting_type": meeting_type,
                "priority": priority,
                "has_decisions": has_decisions,
                "has_action_items": has_action_items
            }
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
    app.run(debug=False, host='0.0.0.0', port=5002)