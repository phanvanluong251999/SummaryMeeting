# Summary Meeting Application

This project is a Flask web application designed to facilitate the transcription and summarization of meeting audio files and documents. It allows users to upload audio files or text documents, which are then processed to extract and summarize the content.

## Project Structure

```
summary-meeting
├── app
│   ├── __init__.py
│   ├── main.py 
│   └── templates
│       └── index.html
├── uploads
├── audio_chunks
├── requirements.txt
└── README.md
```

## Features

- Upload audio files in formats such as MP3, WAV, or M4A.
- Upload text documents in TXT, DOCX, or PDF formats.
- Automatic transcription of audio files using the Whisper model.
- Summarization of transcribed text using OpenAI's GPT-4 model.
- User-friendly web interface for file uploads and displaying results.

## Quick Start

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
- Check Python and FFmpeg installation
- Create a virtual environment
- Install all dependencies
- Create required directories

### Manual Installation

See [INSTALL.md](INSTALL.md) for detailed installation instructions.

**Quick version:**
```bash
# 1. Install FFmpeg (required for audio processing)
#    Windows: choco install ffmpeg
#    macOS:   brew install ffmpeg
#    Linux:   sudo apt install ffmpeg

# 2. Install Python dependencies
pip install -r requirements.txt

# 3. Configure environment (optional)
cp .env.example .env
# Edit .env with your OpenAI API key

# 4. Run the application
python main.py
```

## Running the Application

1. **Start the server:**
   ```bash
   python main.py
   ```

2. **Open your browser** and go to: `http://127.0.0.1:5000`

3. **Upload files:**
   - Audio files: MP3, WAV, M4A
   - Text files: TXT, DOCX, PDF

## ✨ Latest Updates

### 🚀 AssemblyAI Integration (NEW!)
- **Primary transcription provider**: Fast, accurate, supports speaker identification
- **2-5 seconds** for typical meeting audio (vs 30-60s with local model)
- **Free tier**: First 5 hours FREE!
- **Multiple providers**: AssemblyAI → OpenAI Whisper → Local (automatic fallback)

### 🎤 Speaker Identification
- Enable with `ENABLE_SPEAKER_LABELS=true`
- Automatically identifies who said what in meetings
- Perfect for multi-person meetings

### ⚡ Performance
- **AssemblyAI**: 2-5 seconds for 30-second audio
- **OpenAI Whisper**: 2-5 seconds (fallback option)
- **Local model**: 30-60 seconds (free, offline option)

## Contributing

Contributions are welcome! If you have suggestions for improvements or new features, please open an issue or submit a pull request.

## License

This project is licensed under the MIT License. See the LICENSE file for more details.
