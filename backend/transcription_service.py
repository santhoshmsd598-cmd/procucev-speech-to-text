import os
from faster_whisper import WhisperModel

# Use the smaller model by default for Render's free instance.
MODEL_SIZE = os.getenv("WHISPER_MODEL_SIZE", "tiny")

# On a heavily CPU-throttled instance, more threads make inference slower
# (they spin and burn the CPU quota), so default to a single thread.
CPU_THREADS = int(os.getenv("WHISPER_CPU_THREADS", "1"))

USE_VAD = os.getenv("WHISPER_VAD", "true").lower() == "true"

print(
    f"Loading Faster-Whisper model: {MODEL_SIZE} "
    f"(cpu_threads={CPU_THREADS})..."
)

model = WhisperModel(
    MODEL_SIZE,
    device="cpu",
    compute_type="int8",
    cpu_threads=CPU_THREADS,
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
        vad_filter=USE_VAD,
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