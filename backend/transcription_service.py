
import os
from faster_whisper import WhisperModel
MODEL_SIZE = os.getenv("WHISPER_MODEL_SIZE", "base")

print(f"Loading Faster-Whisper model: {MODEL_SIZE}...")

model = WhisperModel(
    MODEL_SIZE,
    device="cpu",
    compute_type="int8"
)

print("Faster-Whisper model loaded successfully!")


def transcribe_audio(audio_path, language=None):
    """
    Transcribe an audio file and return the text and detected language.
    language can be 'en', 'hi', 'ta', or None for automatic detection.
    """
    segments, info = model.transcribe(
        audio_path,
        language=language,
        beam_size=5,
        vad_filter=True
    )

    transcript = " ".join(
        segment.text.strip() for segment in segments
    ).strip()

    return {
        "transcript_text": transcript,
        "language": info.language,
        "language_probability": round(info.language_probability, 4)
    }
