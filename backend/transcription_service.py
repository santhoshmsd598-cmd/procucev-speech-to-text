import os
from faster_whisper import WhisperModel
MODEL_SIZE = os.getenv("WHISPER_MODEL_SIZE", "tiny")
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
    segments, info = model.transcribe(
        audio_path,
        language=language,
        beam_size=1,
        best_of=1,
        vad_filter=USE_VAD,
    )
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