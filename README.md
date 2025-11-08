# 🤖 AI Meeting Summarizer & Assistant

> An intelligent Flask web application that transcribes, summarizes, and enables semantic search across meeting recordings and documents using AI.

[![Python](https://img.shields.io/badge/Python-3.9%2B-blue)](https://www.python.org/)
[![Flask](https://img.shields.io/badge/Flask-3.0%2B-green)](https://flask.palletsprojects.com/)
[![OpenAI](https://img.shields.io/badge/OpenAI-GPT--4-orange)](https://openai.com/)
[![AssemblyAI](https://img.shields.io/badge/AssemblyAI-Audio--to--Text-red)](https://www.assemblyai.com/)
[![ChromaDB](https://img.shields.io/badge/ChromaDB-Vector--DB-purple)](https://www.trychroma.com/)

## 📋 Table of Contents

- [Overview](#overview)
- [Key Features](#key-features)
- [Architecture](#architecture)
- [Quick Start](#quick-start)
- [Installation](#installation)
- [Usage](#usage)
- [Advanced Features](#advanced-features)
- [Configuration](#configuration)
- [Project Structure](#project-structure)
- [API Reference](#api-reference)
- [Troubleshooting](#troubleshooting)
- [Contributing](#contributing)
- [License](#license)

## 🎯 Overview

**AI Meeting Summarizer** is an enterprise-grade solution for automating meeting documentation workflows. It combines state-of-the-art AI models for transcription, summarization, and intelligent question-answering to transform raw meeting recordings into actionable insights.

### What Makes It Special?

- **🎤 Multi-Provider Transcription**: Automatic fallback from AssemblyAI → OpenAI Whisper → Local model
- **🧠 Intelligent Summarization**: GPT-4 powered summaries with structured output
- **🔍 Semantic Search**: ChromaDB vector database for finding relevant meetings by meaning, not just keywords
- **💬 Context-Aware Chatbot**: Ask questions about your meetings using natural language
- **📊 Rich Metadata Extraction**: Automatically extracts participants, roles, actions, duration, topics, and deadlines
- **🌐 Multi-Language Support**: Vietnamese and English with automatic language detection
- **📝 Markdown Preview**: View formatted summaries with beautiful rendering

## ⚡ Key Features

### 1. **Audio & Document Processing**

- **Audio Formats**: MP3, WAV, M4A
- **Document Formats**: TXT, DOCX, PDF
- **Real-Time Streaming**: See transcription progress word-by-word
- **Speaker Identification**: Automatically detect who said what (AssemblyAI)
- **Large File Support**: Up to 100MB

### 2. **AI-Powered Summarization**

- **Structured Summaries**: Meeting info, key points, task assignments
- **Smart Metadata Extraction**:
  - 👥 Participants with roles
  - ⏱️ Duration and time range
  - 📝 Individual action items per person
  - 🏷️ Meeting type classification
  - 🎯 Priority and decision tracking
- **Intelligent Title Generation**: Automatic descriptive titles
- **Date Parsing**: Flexible date extraction from content

### 3. **Vector Search & RAG (Retrieval-Augmented Generation)**

- **Semantic Search**: Find meetings by meaning using ChromaDB embeddings
- **Hybrid Search**: Combines semantic similarity with keyword matching (BM25)
- **Context-Aware Queries**: Remembers previous conversations for follow-up questions
- **Multi-Meeting Analysis**: Query across multiple meetings simultaneously
- **Hallucination Detection**: Validates AI answers against source context
- **Smart Context Truncation**: Optimizes token usage with intelligent chunking

### 4. **Interactive Chatbot**

- **Natural Language Queries**: "What did Dev A work on in the October 10 meeting?"
- **Date & Topic Classification**: Automatically routes queries to relevant meetings
- **Conversation History**: Maintains context across multiple questions
- **Relevance Scoring**: Shows confidence levels for each answer
- **Metadata-Aware**: Leverages rich metadata for precise answers

### 5. **Data Management**

- **Document Browser**: View and manage all stored meetings
- **Full CRUD Operations**: Add, view, update, delete summaries
- **Search & Filter**: Find documents by ID, title, date, or content
- **Markdown Rendering**: Toggle between raw text and formatted preview
- **Export Options**: Download summaries as TXT files

## 🏗️ Architecture

### Technology Stack

```
Frontend:
├── HTML5 + CSS3 (Modern, responsive UI)
├── Vanilla JavaScript (No framework dependencies)
└── Markdown Rendering (marked.js + DOMPurify)

Backend:
├── Flask 3.0+ (Web framework)
├── OpenAI GPT-4 (Summarization & chatbot)
├── AssemblyAI (Primary audio transcription)
└── Python 3.9+ (Runtime)

AI & ML:
├── ChromaDB (Vector database for semantic search)
├── OpenAI Embeddings (text-embedding-3-small)
├── LangChain (Document chunking & text splitting)
├── Sentence Transformers (Cross-encoder re-ranking)
└── Tiktoken (Token counting & context management)

Data Processing:
├── PyPDF2 (PDF extraction)
├── python-docx (DOCX extraction)
└── FFmpeg (Audio processing)
```

### Data Flow

```
┌─────────────┐
│ User Upload │ (Audio/Document)
└──────┬──────┘
       │
       v
┌─────────────────┐
│ File Processing │ → Extract text or transcribe audio
└────────┬────────┘
         │
         v
┌─────────────────┐
│ AI Summarization│ → GPT-4 generates structured summary
└────────┬────────┘
         │
         v
┌─────────────────────────┐
│ Metadata Extraction     │ → Extract participants, actions, duration, topics
└────────┬────────────────┘
         │
         v
┌─────────────────┐
│ ChromaDB Storage│ → Store with embeddings for semantic search
└────────┬────────┘
         │
         v
┌─────────────────┐
│ User Interface  │ → View, search, chat, manage
└─────────────────┘
```

## 🚀 Quick Start

### Prerequisites

- **Python 3.9+**
- **FFmpeg** (for audio processing)
- **OpenAI API Key** (for GPT-4)
- **AssemblyAI API Key** (optional, for faster transcription)

### Automated Setup (Recommended)

**Windows:**

```bash
setup.bat
```

**Linux/macOS:**

```bash
chmod +x setup.sh
./setup.sh
```

The setup script will:

- ✅ Verify Python and FFmpeg installation
- ✅ Create a virtual environment
- ✅ Install all dependencies
- ✅ Create required directories
- ✅ Guide you through API key configuration

### Manual Installation

See [INSTALL.md](INSTALL.md) for detailed step-by-step instructions.

**Quick version:**

```bash
# 1. Install FFmpeg
#    Windows: choco install ffmpeg
#    macOS:   brew install ffmpeg
#    Linux:   sudo apt install ffmpeg

# 2. Clone repository
git clone <your-repo-url>
cd SummaryMeeting

# 3. Create virtual environment
python -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate

# 4. Install dependencies
pip install -r requirements.txt

# 5. Configure environment
cp .env.example .env
# Edit .env with your API keys

# 6. Run application
python main.py
```

### First Run

1. **Start the server:**

   ```bash
   python main.py
   ```

2. **Open your browser:** `http://127.0.0.1:5000`

3. **Upload a test file** and watch the magic happen! 🎩✨

## 📖 Usage

### Uploading Files

1. **Drag & Drop** or click to select a file
2. Supported formats:
   - 🎵 Audio: `.mp3`, `.wav`, `.m4a` (up to 100MB)
   - 📄 Documents: `.txt`, `.docx`, `.pdf`
3. Click **"Tải lên & Xử lý"** (Upload & Process)
4. Watch real-time transcription (for audio files)

### Creating Summaries

1. After upload, click **"Tạo Tóm tắt"** (Generate Summary)
2. Wait for AI to generate structured summary
3. **Edit if needed** using the edit button
4. Click **"Lưu"** (Save) to store in database

### Searching Meetings

**Using the Chatbot:**

```
Examples:
- "Cuộc họp ngày 27/10 bàn về gì?"
- "Dev A làm gì trong sprint này?"
- "Những quyết định quan trọng trong tuần này?"
- "Ai phụ trách authentication module?"
```

**Using the Library:**

- Click 📁 **Library** button
- Browse all meetings
- Filter by date, recent, this week/month
- Search by title, date, or filename

### Managing Data

- Click 💾 **Data Manager** button
- View all documents in ChromaDB
- See full content, metadata, and IDs
- Delete documents if needed
- Toggle markdown preview for formatted viewing

## 🔥 Advanced Features

### 1. **Real-Time Transcription Streaming**

For audio files, watch transcription appear word-by-word:

```python
# Backend automatically streams progress
send_progress(task_id, "Đang hiển thị...", partial_text=accumulated_text)
```

Frontend receives updates via Server-Sent Events (SSE).

### 2. **Context-Aware Chatbot**

The chatbot remembers previous conversations:

```
User: "Cuộc họp ngày 27/10 bàn về gì?"
Bot: [Responds with summary]

User: "Dev A làm gì?"  ← Automatically applies 27/10 meeting context
Bot: [Responds about Dev A in that specific meeting]
```

### 3. **Multi-Meeting Queries**

Ask about multiple meetings at once:

```
"Liệt kê những gì Dev A làm trong mỗi cuộc họp"
→ Searches across ALL discussed meetings
```

### 4. **Intelligent Metadata Extraction**

Automatically extracts:

- **Participants**: Names + roles (e.g., "Dev A (Developer)")
- **Duration**: Actual meeting length in minutes
- **Actions**: Who does what, with deadlines
- **Topics**: Key discussion points
- **Meeting Type**: standup, review, planning, etc.

Example metadata:

```json
{
  "title": "Sprint Planning",
  "date": "2024-10-27",
  "duration_minutes": 65,
  "start_time": "09:00",
  "end_time": "10:05",
  "participants": "Dev A, PM Nam, Tester B",
  "individual_actions": "Dev A: Build API | Tester B: Write tests",
  "meeting_type": "planning"
}
```

### 5. **Hallucination Detection**

AI answers are validated against source context:

```python
validation = validate_answer_grounding(answer, context, client)
# Returns: is_grounded, verification_percentage, confidence
```

Low-confidence answers get a disclaimer automatically.

## ⚙️ Configuration

### Environment Variables

Create a `.env` file:

```bash
# OpenAI API (Required for summarization)
OPENAI_API_KEY=sk-your-api-key-here
OPENAI_BASE_URL=https://api.openai.com/v1

# AssemblyAI (Optional, for faster transcription)
ASSEMBLYAI_API_KEY=your-assemblyai-key-here
ENABLE_SPEAKER_LABELS=true
LANGUAGE_CODE=vi  # or 'en' for English, or leave empty for auto-detect

# ChromaDB Configuration
CHROMA_MODE=local  # or 'cloud' for remote server
CHROMA_HOST=localhost
CHROMA_PORT=8000

# Flask Configuration
SECRET_KEY=your-secret-key-for-sessions
```

### Configuration Options

| Variable                | Default        | Description                  |
| ----------------------- | -------------- | ---------------------------- |
| `OPENAI_API_KEY`        | (required)     | OpenAI API key for GPT-4     |
| `OPENAI_BASE_URL`       | OpenAI default | Custom endpoint URL          |
| `ASSEMBLYAI_API_KEY`    | (optional)     | AssemblyAI for transcription |
| `ENABLE_SPEAKER_LABELS` | `false`        | Speaker identification       |
| `LANGUAGE_CODE`         | auto-detect    | Force language (vi/en)       |
| `CHROMA_MODE`           | `local`        | ChromaDB storage mode        |
| `SECRET_KEY`            | random         | Flask session encryption     |

## 📁 Project Structure

```
SummaryMeeting/
├── main.py                          # Flask application & API routes
├── rag_enhancements.py              # RAG utilities (token counting, validation)
├── semantic_metadata_extractor.py   # Metadata extraction functions
├── requirements.txt                 # Python dependencies
├── .env                            # Environment variables (create from .env.example)
│
├── templates/
│   └── index.html                  # Main UI (single-page application)
│
├── static/
│   └── style.css                   # Modern CSS with dark/light themes
│
├── uploads/                        # Temporary file uploads
├── outputs/                        # Saved meeting summaries (.txt)
├── chroma_db/                      # ChromaDB vector database storage
│
├── bulk_upload_to_chroma.py        # Utility: Import existing summaries
├── clear_chromadb.py               # Utility: Clear database
├── refresh_chromadb.py             # Utility: Refresh from outputs/
├── manage_chromadb.py              # Utility: View & manage data
│
├── setup.bat                       # Windows setup script
├── setup.sh                        # Unix/Linux setup script
│
├── README.md                       # This file
├── INSTALL.md                      # Detailed installation guide
└── CLAUDE.md                       # Architecture & development notes
```

## 📡 API Reference

### Main Endpoints

#### `POST /load_file`

Upload and process a file (audio or document)

**Request:**

```javascript
FormData {
  meeting_file: File,
  stream: "true" (optional, for real-time progress)
}
```

**Response:**

```json
{
  "success": true,
  "filename": "meeting.mp3",
  "text": "transcribed content...",
  "length": 5234,
  "task_id": "1234_meeting.mp3" (if streaming)
}
```

#### `POST /summarize`

Generate AI summary from text

**Request:**

```json
{
  "text": "meeting content..."
}
```

**Response:**

```json
{
  "success": true,
  "summary": "## 1. Meeting Information...",
  "title": "Sprint Planning",
  "date": "2024-10-27"
}
```

#### `POST /save_summary`

Save summary to file and ChromaDB

**Request:**

```json
{
  "summary": "meeting summary...",
  "title": "Sprint Planning",
  "date": "2024-10-27"
}
```

**Response:**

```json
{
  "success": true,
  "filename": "2024-10-27_123456_Sprint_Planning.txt",
  "chromadb_saved": true
}
```

#### `POST /chatbot`

Ask questions about meetings

**Request:**

```json
{
  "question": "Dev A làm gì?",
  "text": "current meeting context (optional)"
}
```

**Response:**

```json
{
  "answer": "Dev A phụ trách...",
  "classification": {"type": "topic", "date": null},
  "meetings": [{...}],
  "count": 3,
  "validation": {"is_grounded": true},
  "context_used": true
}
```

#### `GET /list_meetings`

Get all meetings from ChromaDB

**Response:**

```json
{
  "meetings": [...],
  "grouped": {"2024-10-27": [...]},
  "total": 15
}
```

#### `GET /get_all_data`

Get all documents with full details

**Response:**

```json
{
  "documents": [{
    "id": "doc_id",
    "content": "...",
    "metadata": {...},
    "content_length": 5234
  }],
  "total": 15
}
```

#### `DELETE /delete_document/<doc_id>`

Delete a specific document

**Response:**

```json
{
  "success": true,
  "message": "Document deleted"
}
```

### Utility Scripts

#### Bulk Upload Existing Summaries

```bash
python bulk_upload_to_chroma.py
```

Scans `outputs/` folder and imports all `.txt` summaries to ChromaDB.

#### Clear ChromaDB

```bash
python clear_chromadb.py
```

Removes all documents from ChromaDB (use with caution!).

#### Refresh ChromaDB

```bash
python refresh_chromadb.py
```

Re-imports all summaries from `outputs/` folder (useful after manual edits).

#### Manage ChromaDB

```bash
python manage_chromadb.py
```

Interactive CLI for viewing, searching, and managing documents.

## 🔧 Troubleshooting

### Common Issues

#### 1. **FFmpeg not found**

```bash
# Windows
choco install ffmpeg

# macOS
brew install ffmpeg

# Linux
sudo apt install ffmpeg
```

#### 2. **Module not found errors**

```bash
# Ensure virtual environment is activated
source venv/bin/activate  # Unix
venv\Scripts\activate     # Windows

# Reinstall dependencies
pip install -r requirements.txt
```

#### 3. **OpenAI API errors**

- Check API key in `.env` file
- Verify API endpoint URL
- Check rate limits and quota
- Ensure internet connection

#### 4. **ChromaDB errors**

```bash
# Delete and recreate database
rm -rf chroma_db/
python main.py  # Will recreate automatically
```

#### 5. **Slow transcription**

- Use AssemblyAI for faster results (set `ASSEMBLYAI_API_KEY`)
- Check internet connection speed
- Verify logs show "🚀 Using AssemblyAI..."

#### 6. **Chatbot not finding meetings**

- Check date format (YYYY-MM-DD in database)
- Verify ChromaDB has data: `python manage_chromadb.py`
- Look at logs for "Available dates in database"

### Debug Mode

Enable detailed logging:

```python
# In main.py
logging.basicConfig(level=logging.DEBUG)
```

Check ChromaDB data:

```bash
python manage_chromadb.py
```

## 🤝 Contributing

Contributions are welcome! Here's how you can help:

### Reporting Issues

- Use GitHub Issues
- Include error logs and screenshots
- Describe steps to reproduce

### Submitting Pull Requests

1. Fork the repository
2. Create a feature branch (`git checkout -b feature/amazing-feature`)
3. Commit your changes (`git commit -m 'Add amazing feature'`)
4. Push to the branch (`git push origin feature/amazing-feature`)
5. Open a Pull Request

### Development Setup

```bash
# Install dev dependencies
pip install -r requirements-dev.txt

# Run tests (if available)
pytest

# Format code
black main.py
```

## 📄 License

This project is licensed under the MIT License - see the LICENSE file for details.

## 🙏 Acknowledgments

- **OpenAI** for GPT-4 and Whisper models
- **AssemblyAI** for fast, accurate transcription
- **ChromaDB** for vector database capabilities
- **LangChain** for document processing utilities
- **Flask** community for excellent web framework

## 📞 Support

- **Documentation**: [INSTALL.md](INSTALL.md), [CLAUDE.md](CLAUDE.md)
- **Issues**: GitHub Issues
- **Email**: your-email@example.com

---

Made with ❤️ by **4 Plus+**

**Version**: 2.0.0 | **Last Updated**: November 2024
