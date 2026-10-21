
import os
import io
import wave
import tempfile
import threading

import mysql.connector
from mysql.connector import Error
from dotenv import load_dotenv
from flask import Flask, jsonify, request
from flask_cors import CORS
from flask_socketio import SocketIO, emit

from transcription_service import model, transcribe_audio

load_dotenv()

app = Flask(__name__)
app.config["MAX_CONTENT_LENGTH"] = 25 * 1024 * 1024

frontend_url = os.getenv("FRONTEND_URL", "").rstrip("/")

allowed_origins = [
    "http://localhost:5173",
    "http://localhost:5174",
    "http://127.0.0.1:5173",
    "http://127.0.0.1:5174",
]

if frontend_url:
    allowed_origins.append(frontend_url)

CORS(app, resources={r"/api/*": {"origins": allowed_origins}})

socketio = SocketIO(
    app,
    cors_allowed_origins=allowed_origins,
    async_mode="threading",
)

audio_sessions = {}
audio_sessions_lock = threading.Lock()


def get_db_connection():
    db_host = os.getenv("DB_HOST", "127.0.0.1")
    db_port = int(os.getenv("DB_PORT", "3307"))

    connection_options = {
        "host": db_host,
        "port": db_port,
        "user": os.getenv("DB_USER", "root"),
        "password": os.getenv("DB_PASSWORD", ""),
        "database": os.getenv("DB_NAME", "procucev_speech"),
        "connection_timeout": 15,
    }

    db_ssl = os.getenv("DB_SSL", "auto").lower()

    if db_ssl == "true":
        connection_options["ssl_disabled"] = False
    elif db_ssl == "false":
        connection_options["ssl_disabled"] = True
    elif db_host not in ("localhost", "127.0.0.1"):
        connection_options["ssl_disabled"] = False

    ca_cert = os.getenv("DB_SSL_CA")
    if ca_cert:
        connection_options["ssl_ca"] = ca_cert

    return mysql.connector.connect(**connection_options)


def serialize_transcription(row):
    for field in ("created_at", "updated_at"):
        if row.get(field) is not None:
            row[field] = row[field].isoformat()
    return row


@app.errorhandler(413)
def file_too_large(_error):
    return jsonify({
        "error": "Audio file exceeds the 25 MB limit"
    }), 413


@app.route("/", methods=["GET"])
def home():
    return jsonify({
        "message": "Procucev Speech-to-Text API is running!"
    })


@app.route("/api/health", methods=["GET"])
def health():
    conn = None
    try:
        conn = get_db_connection()
        return jsonify({
            "status": "healthy",
            "database": "connected",
        }), 200
    except Error:
        app.logger.exception("Database health check failed")
        return jsonify({
            "status": "error",
            "database": "disconnected",
        }), 503
    finally:
        if conn is not None and conn.is_connected():
            conn.close()


@app.route("/api/transcriptions", methods=["GET"])
def list_transcriptions():
    conn = None
    cursor = None

    try:
        conn = get_db_connection()
        cursor = conn.cursor(dictionary=True)
        cursor.execute("""
            SELECT id, transcript_text, language, created_at, updated_at
            FROM transcriptions
            ORDER BY created_at DESC
        """)
        rows = cursor.fetchall()
        return jsonify([
            serialize_transcription(row) for row in rows
        ])
    except Error:
        app.logger.exception("Could not list transcriptions")
        return jsonify({
            "error": "Database operation failed"
        }), 500
    finally:
        if cursor:
            cursor.close()
        if conn is not None and conn.is_connected():
            conn.close()


@app.route("/api/transcriptions", methods=["POST"])
def create_transcription():
    data = request.get_json(silent=True) or {}
    transcript = data.get("transcript_text", "")
    language = data.get("language", "auto")

    if not isinstance(transcript, str) or not transcript.strip():
        return jsonify({
            "error": "transcript_text is required"
        }), 400

    if not isinstance(language, str):
        return jsonify({
            "error": "language must be a string"
        }), 400

    conn = None
    cursor = None

    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute("""
            INSERT INTO transcriptions (transcript_text, language)
            VALUES (%s, %s)
        """, (transcript.strip(), language))
        conn.commit()
        new_id = cursor.lastrowid

        return jsonify({
            "id": new_id,
            "transcript_text": transcript.strip(),
            "language": language,
            "message": "Transcription saved",
        }), 201
    except Error:
        app.logger.exception("Could not save transcription")
        return jsonify({
            "error": "Database operation failed"
        }), 500
    finally:
        if cursor:
            cursor.close()
        if conn is not None and conn.is_connected():
            conn.close()


@app.route("/api/transcriptions/<int:transcription_id>", methods=["GET"])
def get_transcription(transcription_id):
    conn = None
    cursor = None

    try:
        conn = get_db_connection()
        cursor = conn.cursor(dictionary=True)
        cursor.execute("""
            SELECT id, transcript_text, language, created_at, updated_at
            FROM transcriptions
            WHERE id = %s
        """, (transcription_id,))
        row = cursor.fetchone()

        if not row:
            return jsonify({
                "error": "Transcription not found"
            }), 404

        return jsonify(serialize_transcription(row))
    except Error:
        app.logger.exception("Could not retrieve transcription")
        return jsonify({
            "error": "Database operation failed"
        }), 500
    finally:
        if cursor:
            cursor.close()
        if conn is not None and conn.is_connected():
            conn.close()


@app.route("/api/transcriptions/<int:transcription_id>", methods=["PUT"])
def update_transcription(transcription_id):
    data = request.get_json(silent=True) or {}
    transcript = data.get("transcript_text")
    language = data.get("language")

    if not isinstance(transcript, str) or not transcript.strip():
        return jsonify({
            "error": "A non-empty transcript_text is required"
        }), 400

    if language is not None and not isinstance(language, str):
        return jsonify({
            "error": "language must be a string"
        }), 400

    conn = None
    cursor = None

    try:
        conn = get_db_connection()
        cursor = conn.cursor()

        if language is None:
            cursor.execute("""
                UPDATE transcriptions
                SET transcript_text = %s
                WHERE id = %s
            """, (transcript.strip(), transcription_id))
        else:
            cursor.execute("""
                UPDATE transcriptions
                SET transcript_text = %s, language = %s
                WHERE id = %s
            """, (transcript.strip(), language, transcription_id))

        conn.commit()

        if cursor.rowcount == 0:
            cursor.execute(
                "SELECT id FROM transcriptions WHERE id = %s",
                (transcription_id,),
            )
            if not cursor.fetchone():
                return jsonify({
                    "error": "Transcription not found"
                }), 404

        return jsonify({
            "message": "Transcription updated"
        })
    except Error:
        app.logger.exception("Could not update transcription")
        return jsonify({
            "error": "Database operation failed"
        }), 500
    finally:
        if cursor:
            cursor.close()
        if conn is not None and conn.is_connected():
            conn.close()


@app.route("/api/transcriptions/<int:transcription_id>", methods=["DELETE"])
def delete_transcription(transcription_id):
    conn = None
    cursor = None

    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute(
            "DELETE FROM transcriptions WHERE id = %s",
            (transcription_id,),
        )
        conn.commit()

        if cursor.rowcount == 0:
            return jsonify({
                "error": "Transcription not found"
            }), 404

        return jsonify({
            "message": "Transcription deleted"
        })
    except Error:
        app.logger.exception("Could not delete transcription")
        return jsonify({
            "error": "Database operation failed"
        }), 500
    finally:
        if cursor:
            cursor.close()
        if conn is not None and conn.is_connected():
            conn.close()


@app.route("/api/transcribe-audio", methods=["POST"])
def transcribe_audio_api():
    audio = request.files.get("audio")

    if not audio or not audio.filename:
        return jsonify({
            "error": "Please upload an audio recording"
        }), 400

    language = request.form.get("language", "auto").strip().lower()

    supported_languages = {
        "auto": None,
        "en": "en",
        "hi": "hi",
        "ta": "ta",
        "en-in": "en",
        "hi-in": "hi",
        "ta-in": "ta",
    }

    if language not in supported_languages:
        return jsonify({
            "error": "Unsupported language. Use auto, en, hi, or ta."
        }), 400

    suffix = os.path.splitext(audio.filename)[1].lower()
    allowed_extensions = {
        ".wav", ".mp3", ".m4a", ".webm",
        ".ogg", ".flac", ".mp4",
    }

    if suffix not in allowed_extensions:
        return jsonify({
            "error": "Unsupported audio format"
        }), 400

    temp_path = None
    conn = None
    cursor = None

    try:
        with tempfile.NamedTemporaryFile(
            suffix=suffix,
            delete=False,
        ) as temp_file:
            temp_path = temp_file.name
            audio.save(temp_path)

        result = transcribe_audio(
            temp_path,
            language=supported_languages[language],
        )
        transcript = result["transcript_text"]

        if not transcript:
            return jsonify({
                "error": "No speech detected"
            }), 422

        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute("""
            INSERT INTO transcriptions (transcript_text, language)
            VALUES (%s, %s)
        """, (transcript, result["language"]))
        conn.commit()

        return jsonify({
            "message": "Audio transcribed and saved successfully",
            "id": cursor.lastrowid,
            "transcript_text": transcript,
            "language": result["language"],
            "language_probability": result["language_probability"],
        }), 201
    except Error:
        app.logger.exception("Database error during audio transcription")
        return jsonify({
            "error": "Could not save transcription to the database"
        }), 500
    except Exception:
        app.logger.exception("Audio transcription failed")
        return jsonify({
            "error": "Audio transcription failed. Check backend logs."
        }), 500
    finally:
        if cursor:
            cursor.close()
        if conn is not None and conn.is_connected():
            conn.close()

        if temp_path and os.path.exists(temp_path):
            try:
                os.remove(temp_path)
            except OSError:
                app.logger.warning("Could not remove temporary audio file")


def pcm_to_wav(pcm_bytes, sample_rate=16000):
    output = io.BytesIO()

    with wave.open(output, "wb") as wav_file:
        wav_file.setnchannels(1)
        wav_file.setsampwidth(2)
        wav_file.setframerate(sample_rate)
        wav_file.writeframes(pcm_bytes)

    return output.getvalue()


def transcribe_pcm(pcm_bytes, language):
    wav_bytes = pcm_to_wav(pcm_bytes)
    segments, info = model.transcribe(
        io.BytesIO(wav_bytes),
        language=None if language == "auto" else language,
        beam_size=1,
        vad_filter=True,
    )

    text = " ".join(
        segment.text.strip() for segment in segments
    ).strip()

    return text, info


@socketio.on("audio_start")
def handle_audio_start(data=None):
    data = data or {}
    language = data.get("language", "auto")

    if language not in {"auto", "en", "hi", "ta"}:
        emit("transcription_error", {
            "error": "Unsupported language. Use auto, en, hi, or ta."
        })
        return

    with audio_sessions_lock:
        audio_sessions[request.sid] = {
            "pcm": bytearray(),
            "language": language,
            "last_processed_bytes": 0,
            "processing": False,
            "lock": threading.Lock(),
        }

    emit("stream_ready", {
        "message": "Audio stream ready",
        "sample_rate": 16000,
    })


@socketio.on("audio_chunk")
def handle_audio_chunk(audio_bytes):
    if not isinstance(audio_bytes, bytes):
        emit("transcription_error", {
            "error": "Expected raw PCM audio bytes"
        })
        return

    with audio_sessions_lock:
        session = audio_sessions.get(request.sid)

    if session is None:
        emit("transcription_error", {
            "error": "Start the audio stream first"
        })
        return

    with session["lock"]:
        session["pcm"].extend(audio_bytes)
        total_bytes = len(session["pcm"])
        bytes_per_three_seconds = 16000 * 2 * 3

        if session["processing"]:
            return

        if total_bytes - session["last_processed_bytes"] < bytes_per_three_seconds:
            return

        session["processing"] = True
        session["last_processed_bytes"] = total_bytes
        audio_snapshot = bytes(session["pcm"])
        language = session["language"]

    try:
        text, info = transcribe_pcm(audio_snapshot, language)
        emit("transcription_update", {
            "transcript_text": text,
            "language": info.language,
            "language_probability": round(
                info.language_probability, 4
            ),
        })
    except Exception:
        app.logger.exception("Streaming transcription failed")
        emit("transcription_error", {
            "error": "Could not transcribe this audio segment"
        })
    finally:
        with session["lock"]:
            session["processing"] = False


@socketio.on("audio_stop")
def handle_audio_stop():
    with audio_sessions_lock:
        session = audio_sessions.get(request.sid)

    if session is None:
        emit("transcription_error", {
            "error": "No active audio stream"
        })
        return

    conn = None
    cursor = None

    try:
        with session["lock"]:
            pcm_bytes = bytes(session["pcm"])
            language = session["language"]

        if len(pcm_bytes) < 2:
            emit("transcription_error", {
                "error": "No audio received"
            })
            return

        wav_bytes = pcm_to_wav(pcm_bytes)
        segments, info = model.transcribe(
            io.BytesIO(wav_bytes),
            language=None if language == "auto" else language,
            beam_size=5,
            vad_filter=True,
        )

        final_text = " ".join(
            segment.text.strip() for segment in segments
        ).strip()

        if not final_text:
            emit("transcription_error", {
                "error": "No speech detected"
            })
            return

        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute("""
            INSERT INTO transcriptions (transcript_text, language)
            VALUES (%s, %s)
        """, (final_text, info.language))
        conn.commit()
        record_id = cursor.lastrowid

        emit("transcription_complete", {
            "id": record_id,
            "transcript_text": final_text,
            "language": info.language,
            "language_probability": round(
                info.language_probability, 4
            ),
            "message": "Transcription saved successfully",
        })
    except Exception:
        app.logger.exception("Final streaming transcription failed")
        emit("transcription_error", {
            "error": "Final transcription or database save failed"
        })
    finally:
        if cursor:
            cursor.close()
        if conn is not None and conn.is_connected():
            conn.close()

        with audio_sessions_lock:
            audio_sessions.pop(request.sid, None)


@socketio.on("disconnect")
def handle_disconnect():
    with audio_sessions_lock:
        audio_sessions.pop(request.sid, None)


if __name__ == "__main__":
    socketio.run(
        app,
        host="127.0.0.1",
        port=int(os.getenv("PORT", "5000")),
        debug=os.getenv("FLASK_DEBUG", "false").lower() == "true",
        use_reloader=False,
    )
