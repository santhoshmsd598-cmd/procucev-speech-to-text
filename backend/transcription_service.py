
import os
from faster_whisper import WhisperModel

# Use the smaller model by default for Render's free instance.
MODEL_SIZE = os.getenv("WHISPER_MODEL_SIZE", "tiny")

print(f"Loading Faster-Whisper model: {MODEL_SIZE}...")

model = WhisperModel(
    MODEL_SIZE,
    device="cpu",
    compute_type="int8",
    cpu_threads=2,
    num_workers=1,
)

print("Faster-Whisper model loaded successfully!")


def transcribe_audio(audio_path, language=None):
    """
    Transcribe an audio file.

    Supported language codes:
    en = English
    hi = Hindi
    ta = Tamil
    None = automatic language detection
    """
    segments, info = model.transcribe(
        audio_path,
        language=language,
        beam_size=1,
        best_of=1,
        vad_filter=True,
    )

    # Consume the generator to finish transcription.
    transcript = " ".join(
        segment.text.strip()
        for segment in segments
    ).strip()

    return {
        "transcript_text": transcript,
        "language": info.language,
        "language_probability": round(
            info.language_probability, 4
        ),
    }
