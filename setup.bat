@echo off
echo ============================================
echo Summary Meeting - Setup Script (Windows)
echo ============================================
echo.

REM Check if Python is installed
python --version >nul 2>&1
if %errorlevel% neq 0 (
    echo [ERROR] Python is not installed or not in PATH
    echo Please install Python 3.9 or higher from https://www.python.org/
    pause
    exit /b 1
)

echo [1/5] Python detected:
python --version
echo.

REM Check if FFmpeg is installed
ffmpeg -version >nul 2>&1
if %errorlevel% neq 0 (
    echo [WARNING] FFmpeg is not installed
    echo FFmpeg is required for audio processing
    echo Install it from: https://ffmpeg.org/download.html
    echo Or use: choco install ffmpeg
    echo.
    pause
)

echo [2/5] Creating virtual environment...
python -m venv venv
if %errorlevel% neq 0 (
    echo [ERROR] Failed to create virtual environment
    pause
    exit /b 1
)
echo Virtual environment created successfully!
echo.

echo [3/5] Activating virtual environment...
call venv\Scripts\activate
echo.

echo [4/5] Installing dependencies...
echo This may take 5-10 minutes (PyTorch is large)...
pip install -r requirements.txt
if %errorlevel% neq 0 (
    echo [ERROR] Failed to install dependencies
    pause
    exit /b 1
)
echo Dependencies installed successfully!
echo.

echo [5/5] Creating required directories...
if not exist "uploads" mkdir uploads
if not exist "outputs" mkdir outputs
if not exist "audio_chunks" mkdir audio_chunks
if not exist "chroma_db" mkdir chroma_db
echo Directories created!
echo.

echo ============================================
echo Setup completed successfully!
echo ============================================
echo.
echo Next steps:
echo 1. Copy .env.example to .env and configure your API keys:
echo    copy .env.example .env
echo    notepad .env
echo.
echo 2. Start the application:
echo    venv\Scripts\activate
echo    python main.py
echo.
echo 3. Open your browser to: http://127.0.0.1:5000
echo.
pause
