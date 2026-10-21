# procucev-speech-to-text
Multilingual speech-to-text application with live transcription and MySQL history  
# SpeakFlow — AI Speech-to-Text

**A multilingual speech-to-text application with live transcription, audio processing, and persistent transcript history.**

SpeakFlow converts spoken audio into text using a self-hosted Faster-Whisper speech recognition model. Users can select a recognition language, view live transcription updates, save transcripts, and manage previously saved records through a clean, modern web interface.

## Features

- **Live Speech Transcription** — Capture microphone audio and receive incremental transcription updates.
- **Multilingual Recognition** — Supports language selection, including English, Hindi, and Tamil.
- **AI-Powered Transcription** — Uses Faster-Whisper for speech recognition.
- **Transcript Editor** — Review and edit saved transcription text.
- **Persistent Storage** — Store and retrieve transcripts using MySQL.
- **Transcription History** — View previously saved transcripts and their timestamps.
- **Update Records** — Edit existing transcript entries.
- **Delete Records** — Remove saved entries when no longer needed.
- **Real-Time Communication** — Uses Socket.IO to transmit audio chunks and deliver transcription updates.
- **Responsive Interface** — Dark-themed UI designed for desktop and mobile screens.

## Tech Stack

| Component | Technology |
|---|---|
| Frontend | React, Vite, CSS |
| Backend | Python, Flask |
| Speech Recognition | Faster-Whisper |
| Database | MySQL |
| Real-Time Communication | Flask-SocketIO, Socket.IO Client |
| API Communication | REST API |
| Version Control | Git, GitHub |

## Project Structure

```text
procucev-speech-to-text/
├── backend/
│   ├── app.py
│   ├── transcription_service.py
│   └── requirements.txt
├── frontend/
│   ├── public/
│   ├── src/
│   │   ├── assets/
│   │   ├── App.jsx
│   │   ├── App.css
│   │   ├── index.css
│   │   └── main.jsx
│   ├── package.json
│   └── vite.config.js
├── .gitignore
└── README.md
```

## Prerequisites

Install the following before running the project:

- Python and a version compatible with the installed dependencies
- Node.js and npm
- MySQL Server
- Git

The Faster-Whisper model downloads model files on first use and requires sufficient disk space and memory.

## Run Locally

### 1. Clone the Repository

```bash
git clone https://github.com/santhoshmsd598-cmd/procucev-speech-to-text.git
cd procucev-speech-to-text
```

### 2. Configure the MySQL Database

Open MySQL and execute the following SQL commands:

```sql
CREATE DATABASE IF NOT EXISTS procucev_speech;

USE procucev_speech;

CREATE TABLE IF NOT EXISTS transcriptions (
    id INT AUTO_INCREMENT PRIMARY KEY,
    transcript_text LONGTEXT NOT NULL,
    language VARCHAR(100) DEFAULT 'auto',
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        ON UPDATE CURRENT_TIMESTAMP
);
```

### 3. Configure the Backend

Open a terminal in the project root:

```bash
cd backend
python -m venv .venv
```

Activate the virtual environment on Windows:

```powershell
.venv\Scripts\activate
```

Install the backend dependencies:

```bash
pip install -r requirements.txt
```

Create a `.env` file inside the `backend` directory with your local MySQL configuration:

```env
DB_HOST=127.0.0.1
DB_PORT=3307
DB_USER=root
DB_PASSWORD=your_mysql_password
DB_NAME=procucev_speech
```

Replace `your_mysql_password` with your actual MySQL password. Keep this file private and never commit database credentials to GitHub.

Start the backend using the startup command configured in `app.py`:

```bash
python app.py
```

The default local backend address is:

`http://127.0.0.1:5000`

### 4. Configure the Frontend

Open a separate terminal in the project root:

```bash
cd frontend
npm install
npm run dev
```

Open the local URL printed by Vite, typically:

`http://localhost:5173`

Ensure the frontend API and Socket.IO URLs match the running backend.

## API Endpoints

| Method | Endpoint | Purpose |
|---|---|---|
| GET | `/api/health` | Check backend health |
| GET | `/api/transcriptions` | Retrieve saved transcripts |
| POST | `/api/transcriptions` | Create a transcript |
| GET | `/api/transcriptions/<id>` | Retrieve a transcript by ID |
| PUT | `/api/transcriptions/<id>` | Update a transcript |
| DELETE | `/api/transcriptions/<id>` | Delete a transcript |
| POST | `/api/transcribe-audio` | Upload audio for transcription |

The application also uses Socket.IO events to stream audio chunks and deliver incremental and final transcription results.

## Security Notes

- Store database credentials and sensitive configuration in environment variables.
- Never upload `.env`, Python virtual environments, or `node_modules` to GitHub.
- Configure production CORS to allow only the deployed frontend origin.
- Use HTTPS and secure database credentials in production.

## Deployment

**Live Application:** To be added after deployment.

The application can be deployed by hosting the React frontend, Flask backend, and MySQL database on compatible cloud services. Update the frontend API and Socket.IO configuration to use the deployed backend.

## Project Objective

The objective of SpeakFlow is to demonstrate an end-to-end speech recognition application combining AI-based transcription, real-time communication, a modern web interface, and persistent database operations.

## Author

**Santhosh M.**

- GitHub: [santhoshmsd598-cmd](https://github.com/santhoshmsd598-cmd)

---

Developed as an AI Speech-to-Text assignment project.
