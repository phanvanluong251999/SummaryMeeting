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

## Requirements

To run this application, you need to install the following dependencies:

- Flask
- PyPDF2
- python-docx
- pydub
- transformers
- OpenAI

You can install the required packages using pip:

```
pip install -r requirements.txt
```

## Running the Application

1. Clone the repository or download the project files.
2. Navigate to the project directory.
3. Install the required dependencies.
4. Run the application:

```
python app/main.py
```

5. Open your web browser and go to `http://127.0.0.1:5000` to access the application.

## Contributing

Contributions are welcome! If you have suggestions for improvements or new features, please open an issue or submit a pull request.

## License

This project is licensed under the MIT License. See the LICENSE file for more details.