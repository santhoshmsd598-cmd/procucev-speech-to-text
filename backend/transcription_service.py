
import os
from faster_whisper import WhisperModel

# Use the smaller model for Render's free instance.
MODEL_SIZE = os.getenv("WHISPER_MODEL_SIZE", "tiny")

print(
    f"Loading Faster-Whisper model: {MODEL_SIZE}...",
    flush=True,
)

model = WhisperModel(
    MODEL_SIZE,
    device="cpu",
    compute_type="int8",
    cpu_threads=1,
    num_workers=1,
)

print(
    "Faster-Whisper model loaded successfully!",
    flush=True,
)


def transcribe_audio(audio_path, language=None):
    """
    Transcribe an audio file.

    Supported languages:
        en = English
        hi = Hindi
        ta = Tamil
        None = automatic language detection
    """
    print("[whisper] Starting audio transcription", flush=True)

    segments, info = model.transcribe(
        audio_path,
        language=language,
        beam_size=1,
        best_of=1,
        vad_filter=True,
        condition_on_previous_text=False,
    )

    # Consume the generator to complete transcription.
    transcript_parts = []

    for segment in segments:
        text = segment.text.strip()

        if text:
            transcript_parts.append(text)

    transcript = " ".join(transcript_parts).strip()

    print(
        f"[whisper] Finished. Characters: {len(transcript)}",
        flush=True,
    )

    return {
        "transcript_text": transcript,
        "language": info.language,
        "language_probability": round(
            info.language_probability, 4
        ),
    }
