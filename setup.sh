#!/bin/bash

echo "============================================"
echo "Summary Meeting - Setup Script (Unix/Mac)"
echo "============================================"
echo ""

# Check if Python is installed
if ! command -v python3 &> /dev/null; then
    echo "[ERROR] Python 3 is not installed"
    echo "Please install Python 3.9 or higher"
    exit 1
fi

echo "[1/5] Python detected:"
python3 --version
echo ""

# Check if FFmpeg is installed
if ! command -v ffmpeg &> /dev/null; then
    echo "[WARNING] FFmpeg is not installed"
    echo "FFmpeg is required for audio processing"
    echo ""
    echo "Install it with:"
    echo "  macOS:  brew install ffmpeg"
    echo "  Ubuntu: sudo apt install ffmpeg"
    echo ""
    read -p "Press Enter to continue anyway..."
fi

echo "[2/5] Creating virtual environment..."
python3 -m venv venv
if [ $? -ne 0 ]; then
    echo "[ERROR] Failed to create virtual environment"
    exit 1
fi
echo "Virtual environment created successfully!"
echo ""

echo "[3/5] Activating virtual environment..."
source venv/bin/activate
echo ""

echo "[4/5] Installing dependencies..."
echo "This may take 5-10 minutes (PyTorch is large)..."
pip install -r requirements.txt
if [ $? -ne 0 ]; then
    echo "[ERROR] Failed to install dependencies"
    exit 1
fi
echo "Dependencies installed successfully!"
echo ""

echo "[5/5] Creating required directories..."
mkdir -p uploads outputs audio_chunks chroma_db
echo "Directories created!"
echo ""

echo "============================================"
echo "Setup completed successfully!"
echo "============================================"
echo ""
echo "Next steps:"
echo "1. Copy .env.example to .env and configure your API keys:"
echo "   cp .env.example .env"
echo "   nano .env  # or use your preferred editor"
echo ""
echo "2. Start the application:"
echo "   source venv/bin/activate"
echo "   python main.py"
echo ""
echo "3. Open your browser to: http://127.0.0.1:5000"
echo ""
