# Installation Guide

This guide will help you set up the Summary Meeting application on your system.

## Prerequisites

### 1. Python
- **Required Version**: Python 3.9 or higher
- Check your Python version:
  ```bash
  python --version
  ```

### 2. FFmpeg (Required for Audio Processing)

FFmpeg is needed by `pydub` to process audio files.

#### Windows
Download and install from: https://ffmpeg.org/download.html

Or use Chocolatey:
```bash
choco install ffmpeg
```

Or use Scoop:
```bash
scoop install ffmpeg
```

#### macOS
```bash
brew install ffmpeg
```

#### Linux (Ubuntu/Debian)
```bash
sudo apt update
sudo apt install ffmpeg
```

#### Verify FFmpeg Installation
```bash
ffmpeg -version
```

## Installation Steps

### 1. Clone or Download the Repository

```bash
git clone <repository-url>
cd SummaryMeeting
```

### 2. Create a Virtual Environment (Recommended)

#### Windows
```bash
python -m venv venv
venv\Scripts\activate
```

#### macOS/Linux
```bash
python3 -m venv venv
source venv/bin/activate
```

### 3. Install Python Dependencies

```bash
pip install -r requirements.txt
```

This will install all required packages:
- Flask (Web framework)
- OpenAI (API client for GPT-4 and Whisper)
- Transformers (For local Whisper model)
- PyTorch (Deep learning framework)
- ChromaDB (Vector database)
- python-docx (DOCX file processing)
- PyPDF2 (PDF file processing)
- pydub (Audio processing)

**Note**: The first installation may take 5-10 minutes as PyTorch is a large package (~2GB).

### 4. Configure Environment Variables (Optional)

Create a `.env` file in the project root:

```bash
# OpenAI API Configuration
OPENAI_API_KEY=your-api-key-here
OPENAI_BASE_URL=https://api.openai.com/v1

# Whisper Configuration (default: true)
USE_WHISPER_API=true

# Flask Configuration
SECRET_KEY=your-secret-key-here
```

**Important**:
- If you don't set environment variables, the app will use the defaults in `main.py`
- The default configuration uses a custom OpenAI endpoint. Replace with your own API key for production use.

### 5. Create Required Directories

The application will create these automatically, but you can create them manually:

```bash
mkdir uploads outputs audio_chunks chroma_db
```

### 6. Run the Application

```bash
python main.py
```

The application will start on: **http://127.0.0.1:5000**

## Verification

### Check if Everything is Working

1. **Open your browser** and go to: http://127.0.0.1:5000
2. **Upload a test file** (text or audio)
3. **Check the console logs** - you should see:
   ```
   🚀 Using OpenAI Whisper API for transcription...
   ✅ Transcription completed via API
   ```

### Test ChromaDB

Run the data viewer utility:

```bash
python view_data.py
```

This will show all stored meetings in ChromaDB.

## Troubleshooting

### Issue: "FFmpeg not found"
**Solution**: Install FFmpeg (see Prerequisites section above)

### Issue: "Module not found" errors
**Solution**: Make sure you're in the virtual environment and run:
```bash
pip install -r requirements.txt
```

### Issue: PyTorch installation fails
**Solution**: Install PyTorch separately first:
```bash
# CPU version (smaller, faster to install)
pip install torch --index-url https://download.pytorch.org/whl/cpu

# Then install other requirements
pip install -r requirements.txt
```

### Issue: "OpenAI API error"
**Solution**:
- Check your API key in environment variables or `main.py`
- Verify your API endpoint URL is correct
- Ensure you have internet connection

### Issue: Slow transcription even with API
**Solution**:
- Verify `USE_WHISPER_API=true` in your environment
- Check logs to confirm API is being used (look for 🚀 emoji)
- Test your internet connection speed

### Issue: ChromaDB errors
**Solution**:
- Delete the `chroma_db/` directory and let it recreate
- Check that you have write permissions in the project directory

## Optional: GPU Support (Advanced)

For faster local Whisper transcription, install PyTorch with CUDA:

### NVIDIA GPU (CUDA 11.8)
```bash
pip uninstall torch
pip install torch torchvision torchaudio --index-url https://download.pytorch.org/whl/cu118
```

### NVIDIA GPU (CUDA 12.1)
```bash
pip uninstall torch
pip install torch torchvision torchaudio --index-url https://download.pytorch.org/whl/cu121
```

Verify GPU is available:
```python
import torch
print(torch.cuda.is_available())  # Should print: True
```

## Development Mode

To run in development mode with auto-reload:

```bash
# Already enabled in main.py
python main.py
```

Flask debug mode is enabled by default in `main.py` (line 843).

## Production Deployment

For production, use a WSGI server like Gunicorn:

```bash
pip install gunicorn
gunicorn -w 4 -b 0.0.0.0:5000 main:app
```

Or use Docker (create a Dockerfile):
```dockerfile
FROM python:3.11-slim
WORKDIR /app
COPY requirements.txt .
RUN apt-get update && apt-get install -y ffmpeg
RUN pip install -r requirements.txt
COPY . .
CMD ["python", "main.py"]
```

## Next Steps

- Read the [README.md](README.md) for feature overview
- Check [CLAUDE.md](CLAUDE.md) for architecture details
- Start uploading your meeting files!

## Support

If you encounter issues:
1. Check the console logs for error messages
2. Verify all prerequisites are installed
3. Ensure your API keys are correct
4. Try running `view_data.py` to debug ChromaDB
