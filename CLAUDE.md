# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

This is a Flask-based meeting transcription and summarization application that:
- Accepts audio files (MP3, WAV, M4A) or text documents (TXT, DOCX, PDF)
- Transcribes audio using AssemblyAI API with real-time progress streaming
- Generates meeting summaries using GPT-4o-mini (OpenAI)
- Stores summaries in ChromaDB for semantic search
- Provides an AI chatbot interface for querying past meetings

## Architecture

### Core Application Structure

- **main.py**: Main Flask application containing all routes, business logic, and initialization
- **view_data.py**: Standalone utility script to inspect ChromaDB contents
- **templates/index.html**: Single-page web interface with embedded JavaScript for UI interactions
- **static/style.css**: CSS styling (may be embedded in HTML)

### Key Components

1. **File Processing Pipeline**
   - Text extraction: TXT, DOCX, PDF → raw text
   - Audio processing: MP3/WAV/M4A → transcription via AssemblyAI API
   - Real-time progress streaming for audio transcription

2. **AI Integration**
   - **AssemblyAI** (main.py:320-409): Audio-to-text transcription
     - Fast processing (typically 2-5 seconds for short audio)
     - Optional speaker labels (identifies who said what)
     - Language auto-detection or manual specification
     - Real-time progress updates via Server-Sent Events (SSE)
   - **OpenAI GPT-4o-mini** (used for summarization and chatbot ONLY):
     - Meeting summary generation: Creates structured summaries
     - Chatbot: RAG-based Q&A using ChromaDB semantic search
   - Main AI operations:
     - Audio transcription: AssemblyAI API (main.py:320-409)
     - Summary generation: OpenAI GPT-4o-mini
     - Chatbot Q&A: OpenAI GPT-4o-mini with ChromaDB context

3. **ChromaDB Vector Store** (main.py:62-223)
   - Persistent storage in `chroma_db/` directory
   - Collection: "meeting_summaries"
   - Embedding function: text-embedding-3-small via OpenAI
   - Functions:
     - `save_summary_to_chromadb()`: Stores summaries with metadata
     - `search_meetings_chromadb()`: Semantic search with optional date filtering
     - `get_meeting_by_date_chromadb()`: Date-based retrieval
     - `get_all_meeting_dates_chromadb()`: List all unique dates

4. **Session Management**
   - Flask sessions store pending summaries before user saves
   - Chat history maintained in session (last 20 messages)
   - Allows user to edit summary/title before saving

### Data Flow

1. **Upload → Summary → Save**:
   - User uploads file → `/load_file` extracts text
   - User clicks summarize → `/summarize` generates summary (stored in session)
   - User edits and clicks save → `/save_summary` writes to file + ChromaDB

2. **Chatbot Query**:
   - User asks question → `/chatbot` endpoint
   - Question classification (date-based vs topic-based)
   - ChromaDB semantic search (with optional date filter)
   - GPT-4o-mini generates answer using retrieved context
   - Returns answer with meeting references

### Important Configuration (main.py:27-47)

- **API Keys** (in .env file):
  - `ASSEMBLYAI_API_KEY`: AssemblyAI API key for audio transcription
  - `OPENAI_API_KEY`: OpenAI API key for summarization and chatbot
  - `OPENAI_BASE_URL`: Custom OpenAI endpoint URL
- **AssemblyAI Options**:
  - `ENABLE_SPEAKER_LABELS`: Enable/disable speaker identification (default: false)
  - `LANGUAGE_CODE`: Language for transcription (e.g., 'en', 'vi', or empty for auto-detect)
- **Directories**: `uploads/`, `outputs/`, `chroma_db/`
- **Max file size**: 100MB
- **Supported formats**:
  - Audio: .mp3, .wav, .m4a
  - Text: .txt, .docx, .pdf

## Development Commands

### Running the Application

```bash
python main.py
```
- Starts Flask server on `0.0.0.0:5000`
- Debug mode enabled by default
- Access at: `http://127.0.0.1:5000`

### Viewing ChromaDB Data

```bash
python view_data.py
```
- Displays all stored meetings with metadata
- Shows statistics (meetings per date, character counts)
- Tests semantic search functionality
- Useful for debugging ChromaDB storage

### Installing Dependencies

```bash
pip install -r requirements.txt
```

This installs all required packages:
- flask, python-dotenv (web framework)
- openai, assemblyai (AI APIs)
- PyPDF2, python-docx (document processing)
- chromadb (vector database)

### Testing Audio Transcription

**Setup AssemblyAI:**
1. Get free API key from https://www.assemblyai.com/dashboard/signup (5 hours free)
2. Set `ASSEMBLYAI_API_KEY` in .env file
3. Upload audio file - transcription completes in 2-5 seconds with real-time progress!

## File Processing Details

### Audio Processing

**AssemblyAI Transcription (main.py:320-409):**
- Uploads audio file directly to AssemblyAI (no chunking needed)
- Real-time progress updates via Server-Sent Events (SSE)
- Optional speaker labels: Identifies "who said what"
- Language auto-detection or manual specification
- Fast processing: typically 2-5 seconds for short meeting audio
- Progress stages:
  1. Khởi tạo phiên chuyển đổi... (5%)
  2. Đang tải file lên AssemblyAI... (20%)
  3. Đang xử lý âm thanh, vui lòng đợi... (40%)
  4. Đang định dạng kết quả... (80%)
  5. Hoàn thành! (100%)

### Text Extraction (main.py:314-343)

- **TXT**: Direct UTF-8 file read
- **DOCX**: Uses python-docx, concatenates paragraphs
- **PDF**: Uses PyPDF2, extracts text from all pages

### Date Parsing (main.py:250-260)

- Regex pattern: `\d{1,2}[/-]\d{1,2}[/-]\d{4}`
- Normalizes to YYYY-MM-DD format
- Falls back to current date if not found

## API Endpoints

- `GET /`: Main web interface
- `POST /load_file`: Upload and process file (audio or text)
- `POST /summarize`: Generate meeting summary using AI
- `POST /save_summary`: Save summary to file and ChromaDB
- `POST /chatbot`: Ask questions about meetings (RAG-based)
- `GET /list_meetings`: List all meetings in ChromaDB
- `POST /search_meetings`: Semantic search for meetings

## Important Notes

### ChromaDB Considerations

- Collection uses OpenAI embeddings (text-embedding-3-small)
- Document IDs format: `{date}_{filename}` (without .txt extension)
- Metadata includes: title, date, filename, created_at, text_length
- Semantic search returns documents with distance scores (lower = more relevant)

### Session Data

- `pending_summary`: Holds summary data before save (allows editing)
- `chat_history`: Last 20 chat messages for context
- Cleared after save operation

### Error Handling

- File size limit enforced via Flask config (100MB)
- Custom error handlers for 413 (too large) and 500 (server error)
- Extensive logging throughout application (INFO level)

### Output Format

Summaries saved to `outputs/` with filename pattern:
```
{date}_{timestamp}_{sanitized_title}.txt
```

Format includes header with metadata (title, date, generated timestamp) and structured summary.

## Chatbot Implementation Details

The chatbot (main.py:626-760) uses a two-step RAG approach:

1. **Classification**: Uses function calling to determine if query is date-based or topic-based
2. **Retrieval**: Semantic search in ChromaDB (with date filter if applicable)
3. **Generation**: GPT-4o-mini generates answer using full meeting summaries as context
4. **Response**: Includes answer + metadata about source meetings (title, date, relevance score)

Current date/time context injected for relative date queries (e.g., "yesterday", "last week").

## Directory Structure

```
SummaryMeeting/
├── main.py              # Main Flask application
├── view_data.py         # ChromaDB inspection utility
├── templates/
│   └── index.html       # Web interface
├── static/
│   └── style.css        # Styling
├── uploads/             # User-uploaded files
├── outputs/             # Generated summaries (txt files)
├── inputs/              # Sample input files
├── audio_chunks/        # Temporary audio chunks (auto-cleaned)
└── chroma_db/           # ChromaDB persistent storage (created on first run)
```

## Language

- Web interface: Vietnamese
- Code/comments: Mixed English and Vietnamese
- AI prompts: Bilingual (detects transcript language for summaries)
- Chatbot responses: Vietnamese by default
