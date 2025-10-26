# Quick Start Guide

Get your meeting summarization app running in 5 minutes!

## Prerequisites

- Python 3.9+ installed
- FFmpeg installed (for audio processing)

## Step 1: Get API Keys (2 minutes)

### AssemblyAI (for transcription) - **REQUIRED**
1. Go to https://www.assemblyai.com/dashboard/signup
2. Sign up for free account
3. Get your API key from the dashboard
4. **Free tier**: First 5 hours of transcription FREE! 🎉

### OpenAI (for summarization) - **REQUIRED**
1. Go to https://platform.openai.com/signup
2. Create account and add payment method
3. Get API key from https://platform.openai.com/api-keys
4. **Cost**: Very affordable (~$0.01 per meeting summary)

## Step 2: Install (2 minutes)

### Option A: Automated (Recommended)

**Windows:**
```bash
setup.bat
```

**Linux/Mac:**
```bash
chmod +x setup.sh
./setup.sh
```

### Option B: Manual
```bash
# Install dependencies
pip install -r requirements.txt

# Create directories
mkdir uploads outputs audio_chunks chroma_db
```

## Step 3: Configure (1 minute)

Create a `.env` file:

```bash
# Copy template
copy .env.example .env    # Windows
cp .env.example .env      # Linux/Mac
```

Edit `.env` and add your API keys:

```env
# AssemblyAI (for speech-to-text)
ASSEMBLYAI_API_KEY=your-assemblyai-key-here

# OpenAI (for summarization)
OPENAI_API_KEY=sk-your-openai-key-here
OPENAI_BASE_URL=https://api.openai.com/v1

# Provider (keep as assemblyai)
STT_PROVIDER=assemblyai

# Optional: Enable speaker identification
ENABLE_SPEAKER_LABELS=false
```

## Step 4: Run! 🚀

```bash
python main.py
```

Open your browser to: **http://127.0.0.1:5000**

## Step 5: Test It Out

### Upload Your First Meeting

1. **Drag and drop** an audio file (MP3, WAV, M4A) or text document (TXT, DOCX, PDF)
2. Click **"Tải file"** (Upload file)
3. Wait 2-5 seconds for transcription ⚡
4. Review the transcript
5. Click **"Tạo bản tóm tắt"** (Create summary)
6. Edit the summary if needed
7. Click **"Lưu"** (Save)

### Try the Chatbot

1. Go to the **Chatbot** tab
2. Ask questions like:
   - "What was discussed in yesterday's meeting?"
   - "What are the action items from this week?"
   - "Summarize all meetings from October"

## Features

### ⚡ Fast Transcription
- **AssemblyAI**: 2-5 seconds for 30-second audio
- Automatic fallback to OpenAI if AssemblyAI fails
- Final fallback to local model (free but slow)

### 🎤 Speaker Identification (Optional)
Enable in `.env`:
```env
ENABLE_SPEAKER_LABELS=true
```

Transcripts will show:
```
Speaker A: Welcome everyone to today's meeting.
Speaker B: Thank you for having me.
```

### 📝 Smart Summaries
- Generates structured summaries with:
  - Brief Overview
  - Key Discussion Points
  - Decisions Made
  - Action Items
- Detects language automatically (works in English, Vietnamese, etc.)

### 💬 AI Chatbot
- Ask questions about past meetings
- Semantic search powered by ChromaDB
- Answers with references to specific meetings

### 🔍 Meeting Search
- Search by date: "What happened on October 15?"
- Search by topic: "Tell me about budget discussions"
- View all meetings in the list

## Cost Estimates

### AssemblyAI (Transcription)
- **Free tier**: 5 hours free
- **Paid**: $0.00025/second = $0.015/minute = $0.90/hour
- **Example**: 10 meetings/week (5 min avg) = ~$0.30/week

### OpenAI (Summarization)
- **GPT-4o-mini**: ~$0.01-0.03 per summary
- **Example**: 10 summaries/week = ~$0.20/week

**Total cost**: ~$0.50/week for typical usage 💰

## Switching Providers

### Use OpenAI Whisper Instead
Edit `.env`:
```env
STT_PROVIDER=openai
```

### Use Free Local Model
Edit `.env`:
```env
STT_PROVIDER=local
```
⚠️ First transcription will download ~500MB model and take 30-60 seconds

## Troubleshooting

### "AssemblyAI API key not provided"
- Check your `.env` file exists in the project root
- Verify `ASSEMBLYAI_API_KEY` is set correctly
- Restart the application

### "FFmpeg not found"
Install FFmpeg:
- **Windows**: `choco install ffmpeg`
- **Mac**: `brew install ffmpeg`
- **Linux**: `sudo apt install ffmpeg`

### Transcription is slow
- Verify you're using AssemblyAI (check logs for 🚀 emoji)
- Check your internet connection
- Try switching providers: `STT_PROVIDER=openai`

### "Module not found"
```bash
pip install -r requirements.txt
```

## Next Steps

- Read [INSTALL.md](INSTALL.md) for detailed installation
- Check [CLAUDE.md](CLAUDE.md) for architecture details
- Read [README.md](README.md) for features overview

## Support

Having issues? Check the logs in your console for detailed error messages.

---

**Enjoy your fast, AI-powered meeting summaries! 🎉**
