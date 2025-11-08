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

### 6. **Detailed Chatbot Flow (Step-by-Step)**

The chatbot processes your questions through multiple stages to provide accurate, context-aware answers:

#### **Stage 1: Input Reception & Session Management**
```
User Input: "Cuộc họp ngày 27/10 bàn về gì?"
   ↓
1. Load current session state:
   - Chat history (last 20 messages)
   - Current meeting context (if any)
   - Previously discussed meetings list

2. Clear session on new page load (automatic):
   - POST /clear_session endpoint called on page load
   - Resets: current_meeting_context, discussed_meetings, chat_history
   - Ready for fresh conversation
```

#### **Stage 2: Question Classification & Intent Detection**

```
Question: "Cuộc họp ngày 27/10 bàn về gì?"
   ↓
📊 CLASSIFICATION LAYER:

A) Date/Topic Classification (via GPT function calling):
   - Detects date-based queries: "cuộc họp ngày X"
   - Detects topic-based queries: "bàn về X", "meeting nào đề cập X"
   - Extracts date if present: "27/10" → "2024-10-27"
   - Classification type: "date" or "topic"

B) Query Intention Classification (via keyword analysis):
   - Analyzes: person_focused, task_focused, decision_focused, time_focused, etc.
   - Confidence score: 0-1.0
   - Extracted entities: people names, keywords, search indicators
   - is_followup_question: True/False (affects context handling)

C) General Question Detection (NEW):
   - Keywords: "bao nhiêu", "tất cả", "tổng", "danh sách"
   - If detected: searches ALL meetings (no date filter)
   - Example: "Có tất cả bao nhiêu cuộc họp" → is_general_question=True
```

#### **Stage 3: Context-Aware Search Strategy**

```
   ↓
🔍 SEARCH STRATEGY DECISION:

Based on classification, determine search scope:

SCENARIO 1: Date-based query
   Q: "Cuộc họp ngày 27/10 bàn về gì?"
   → date_filter = "2024-10-27"
   → Search ONLY meetings on that date
   → is_context_query = True

SCENARIO 2: Follow-up question (with existing context)
   Q1: "Cuộc họp ngày 27/10 bàn về gì?" → Sets context to 2024-10-27
   Q2: "Dev A làm gì?"
   → is_followup_question = True
   → Use current_meeting_context = "2024-10-27"
   → date_filter = "2024-10-27"
   → is_context_query = True

SCENARIO 3: New search query (across all meetings)
   Q: "meeting nào đề cập Database tối ưu cho search"
   → is_followup_question = False (has search keywords)
   → is_general_question = False
   → date_filter = None
   → Search ALL meetings
   → Updates context to top result meeting

SCENARIO 4: General/Statistics query
   Q: "Có tất cả bao nhiêu cuộc họp"
   → is_general_question = True
   → date_filter = None (SKIP context filter)
   → Search ALL meetings
   → DON'T filter results by context
```

#### **Stage 4: Semantic Vector Search (ChromaDB)**

```
   ↓
🔎 SEMANTIC SEARCH:

A) Query Preparation:
   - Current question text
   - Optional: date filter (if date-based)
   - Optional: metadata filters (meeting type, has actions, etc.)

B) Embedding Generation:
   - Question converted to vector using OpenAI embeddings (text-embedding-3-small)
   - Vector: 1536 dimensions

C) ChromaDB Search:
   - Compare question embedding with all meeting summaries
   - Apply where_filter if date/context specified
   - Returns top 10 semantic matches with similarity scores

D) Intention-Based Filtering:
   - If task_focused: prioritize documents with action items
   - If person_focused: prioritize documents mentioning specific people
   - If decision_focused: prioritize documents with decision info
   - Apply similarity threshold based on intention type

E) Context Filtering (CRITICAL FIX):
   - IF is_followup_question=True AND current_context exists AND NOT is_general_question:
     → Keep only results from context meeting date
   - IF is_general_question=True:
     → Use ALL results (no filtering)
   - Result: 1-6 most relevant documents
```

#### **Stage 5: Context Building & Token Management**

```
   ↓
📚 CONTEXT PREPARATION:

For each search result (top 6):

A) Extract Meeting Metadata:
   - Title, date, participants, duration
   - Meeting type, individual actions
   - Participant roles and information

B) Build Rich Context:
   ```
   ════════════════════════════════════════
   [MEETING 1]
   📅 Date: 2024-10-27
   📌 Title: Sprint Planning Review
   🏷️ Type: planning
   👥 Participants: Dev A (Developer), PM Nam (PM), Tester B (Tester)
   ⏱️ Duration: 65 minutes (09:00 - 10:05)
   📝 Individual Actions:
      • Dev A: Build authentication API (deadline: 2024-10-30)
      • Tester B: Write integration tests
   🎯 Relevance Score: 92%

   📄 CONTENT:
   [Full meeting summary text...]
   ════════════════════════════════════════
   ```
C) Smart Token Truncation:
   - Count tokens for entire context
   - If exceeds 6000 tokens (max for GPT-4o-mini):
     → Intelligently chunk by meeting sections
     → Keep most relevant sections
     → Compress less important details
   - Final context: optimized for accuracy without exceeding limits
```

#### **Stage 6: System Prompt Engineering & AI Generation**

```
   ↓
🤖 AI ANSWER GENERATION:

A) Dynamic System Prompt:
   - Base instruction: "You are an intelligent meeting assistant"
   - Query intention guidance (adapted to question type)
   - Special instructions for general questions:
     "⭐ This is a statistics question - answer based on ALL meetings"
   - Metadata usage guide: How to use participants, actions, roles
   - Strict accuracy requirements: No hallucinations, must cite sources

B) Chat History Integration:
   - Include last 10 user-assistant exchanges
   - GPT understands conversation context
   - Helps with pronoun resolution ("this meeting" → previous meeting)

C) GPT-4o-mini Generation:
   - Input: [System Prompt] + [Chat History] + [Context] + [Question]
   - Temperature: 0 (maximum accuracy, no randomness)
   - Max tokens: 1500
   - Response format: Flexible (JSON or plain text)

D) Response Parsing:
   - Try 4 parsing strategies:
     1. Direct JSON parsing
     2. Extract from code blocks
     3. Extract with balanced braces
     4. Create JSON from plain text response
   - Result: Structured answer + meeting titles
```

#### **Stage 7: Validation & Hallucination Detection**

```
   ↓
✅ ANSWER VALIDATION:

A) Grounding Check:
   - Is the answer supported by context?
   - Can we find evidence in meeting summaries?
   - Confidence level: high/medium/low

B) Verification Process:
   - GPT validates answer against context
   - Generates verification percentage
   - If low confidence (< 50%): Add disclaimer

C) Confidence Assessment:
   - High: "Based on the meeting summary..."
   - Medium: "According to the meeting, it appears..."
   - Low: "⚠️ I couldn't find clear information..."

Example disclaimer:
   "Note: This answer has lower confidence. Please refer to the original
    meeting summary for verification."
```

#### **Stage 8: Session Update & Response Assembly**

```
   ↓
💾 SESSION STATE UPDATE:

A) Chat History:
   - Add user question to history
   - Add AI answer to history
   - Keep last 20 messages for context

B) Meeting Context Update (CRITICAL):
   - If NEW SEARCH (is_followup=False):
     → Update current_meeting_context to top result meeting
     → Set context_was_just_updated = True
   - If FOLLOW-UP (is_followup=True):
     → Keep current context unchanged

C) Multi-Meeting Tracking:
   - Add new meeting to discussed_meetings list
   - Track up to 5 meetings in conversation
   - Used for "each/all meetings" queries

Example state after Q1:
   current_meeting_context = {
     date: '2024-10-27',
     title: 'Sprint Planning Review',
     id: 'doc_123'
   }
   discussed_meetings = [{date: '2024-10-27', title: '...', id: '...'}]
```

#### **Stage 9: Final Response & Debugging Info**

```
   ↓
📤 RETURN RESPONSE:

```json
{
  "answer": "Cuộc họp ngày 27/10 bàn về Sprint Planning...",

  "classification": {
    "type": "date",
    "date": "2024-10-27"
  },

  "query_intention": {
    "type": "topic_focused",
    "confidence": 0.85,
    "reasoning": "Query detected as topic_focused...",
    "extracted_entities": {
      "people": [],
      "keywords": ["sprint", "planning"]
    }
  },

  "meetings": [
    {
      "date": "2024-10-27",
      "title": "Sprint Planning Review",
      "relevance": 92.5,
      "id": "doc_123"
    }
  ],

  "count": 1,

  "validation": {
    "is_grounded": true,
    "confidence": "high"
  },

  "search_stats": {
    "semantic_results": 1,
    "context_tokens": 2345,
    "search_type": "semantic_with_intention_filtering"
  },

  "context_used": true,
  "current_meeting": {date: '2024-10-27', title: '...'},
  "discussed_meetings": [{...}]
}
```
```

#### **Complete Example Flow: Q4 → Q5**

```
Q4: "meeting nào đề cập Database cần tối ưu cho search không?"
   ↓
Stage 2: is_followup_question=False (has "meeting nào", "đề cập")
        is_general_question=False
        intention_type=topic_focused
   ↓
Stage 3: NEW SEARCH mode (not a follow-up)
        date_filter=None (search all)
   ↓
Stage 4: Find top match = 2024-10-17 meeting (Design Review)
        similarity=0.89
   ↓
Stage 5-6: Build context, generate answer
   ↓
Stage 8: UPDATE context!
        current_meeting_context = {date: '2024-10-17', title: 'Design Review'}

Q5: "có những ai trong cuộc họp này?"
   ↓
Stage 2: is_followup_question=True (no search keywords)
        is_general_question=False
   ↓
Stage 3: FOLLOW-UP mode
        Use current_meeting_context['date'] = '2024-10-17' ← UPDATED!
        date_filter='2024-10-17'
   ↓
Stage 4: Search only 2024-10-17 meeting
        Find participant info from Design Review
   ↓
Stage 5-9: Generate answer about 2024-10-17 meeting participants ✅
```

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
