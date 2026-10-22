
import { useCallback, useEffect, useRef, useState } from "react";
import {
  Mic,
  Square,
  Save,
  Trash2,
  RefreshCw,
  X,
  LoaderCircle,
  Radio,
} from "lucide-react";
import { io } from "socket.io-client";
import "./App.css";

const API =
  import.meta.env.VITE_API_URL || "http://127.0.0.1:5000/api";
const SOCKET_URL =
  import.meta.env.VITE_SOCKET_URL || "http://127.0.0.1:5000";
const TARGET_SAMPLE_RATE = 16000;

const languageMap = {
  "en-IN": "en",
  "en-US": "en",
  "hi-IN": "hi",
  "ta-IN": "ta",
};

function downsampleToPCM16(input, inputSampleRate) {
  if (inputSampleRate < TARGET_SAMPLE_RATE) {
    throw new Error("Your microphone sample rate is too low.");
  }

  const ratio = inputSampleRate / TARGET_SAMPLE_RATE;
  const outputLength = Math.floor(input.length / ratio);
  const pcm = new Int16Array(outputLength);

  for (let i = 0; i < outputLength; i++) {
    const start = Math.floor(i * ratio);
    const end = Math.min(Math.floor((i + 1) * ratio), input.length);

    let sum = 0;
    let count = 0;

    for (let j = start; j < end; j++) {
      sum += input[j];
      count++;
    }

    const sample = count ? sum / count : 0;
    const clamped = Math.max(-1, Math.min(1, sample));

    pcm[i] =
      clamped < 0
        ? Math.round(clamped * 32768)
        : Math.round(clamped * 32767);
  }

  return pcm;
}

export default function App() {
  const [transcript, setTranscript] = useState("");
  const [history, setHistory] = useState([]);
  const [recording, setRecording] = useState(false);
  const [processing, setProcessing] = useState(false);
  const [status, setStatus] = useState("Ready");
  const [language, setLanguage] = useState("en-IN");
  const [editingId, setEditingId] = useState(null);
  const [loading, setLoading] = useState(false);

  const socketRef = useRef(null);
  const streamRef = useRef(null);
  const audioContextRef = useRef(null);
  const sourceRef = useRef(null);
  const processorRef = useRef(null);
  const muteGainRef = useRef(null);
  const stoppingRef = useRef(false);
  const savedTextRef = useRef("");
  const recordingRef = useRef(false);
  const processingRef = useRef(false);
  const mountedRef = useRef(false);

  const loadHistory = useCallback(async () => {
    try {
      setLoading(true);

      const response = await fetch(`${API}/transcriptions`);
      const data = await response.json();

      if (!response.ok) {
        throw new Error(data.error || "Could not load history.");
      }

      setHistory(Array.isArray(data) ? data : []);
    } catch (error) {
      setStatus(error.message || "Cannot connect to the backend.");
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    loadHistory();
  }, [loadHistory]);

  const releaseAudio = useCallback(async () => {
    if (processorRef.current) {
      processorRef.current.onaudioprocess = null;

      try {
        processorRef.current.disconnect();
      } catch {}

      processorRef.current = null;
    }

    if (sourceRef.current) {
      try {
        sourceRef.current.disconnect();
      } catch {}

      sourceRef.current = null;
    }

    if (muteGainRef.current) {
      try {
        muteGainRef.current.disconnect();
      } catch {}

      muteGainRef.current = null;
    }

    if (streamRef.current) {
      streamRef.current.getTracks().forEach((track) => track.stop());
      streamRef.current = null;
    }

    if (audioContextRef.current) {
      const context = audioContextRef.current;
      audioContextRef.current = null;

      if (context.state !== "closed") {
        try {
          await context.close();
        } catch {}
      }
    }
  }, []);

  const finishRecording = useCallback(async () => {
    await releaseAudio();
    recordingRef.current = false;
    stoppingRef.current = false;
    setRecording(false);
  }, [releaseAudio]);

  const createSocket = useCallback(() => {
    return new Promise((resolve, reject) => {
      const socket = io(SOCKET_URL, {
        transports: ["websocket", "polling"],
        timeout: 20000,
        reconnection: false,
      });

      socketRef.current = socket;

      let settled = false;

      const timeout = window.setTimeout(() => {
        if (!settled) {
          settled = true;
          socket.disconnect();
          socketRef.current = null;
          reject(
            new Error("Could not connect to the transcription server.")
          );
        }
      }, 21000);

      socket.once("connect", () => {
        if (settled) return;

        settled = true;
        window.clearTimeout(timeout);
        resolve(socket);
      });

      socket.once("connect_error", (error) => {
        if (settled) return;

        settled = true;
        window.clearTimeout(timeout);
        socket.disconnect();
        socketRef.current = null;

        reject(
          new Error(`WebSocket connection failed: ${error.message}`)
        );
      });

      socket.on("stream_ready", () => {
        setStatus("Connected. Listening to your microphone...");
      });

      socket.on("transcription_update", (data) => {
        if (data.transcript_text) {
          setTranscript(data.transcript_text);
          savedTextRef.current = data.transcript_text;

          setStatus(
            `Live transcription · Detected language: ${
              data.language || "detecting"
            }`
          );
        }
      });

      socket.on("transcription_complete", async (data) => {
        await finishRecording();

        setTranscript(data.transcript_text || "");
        savedTextRef.current = data.transcript_text || "";
        setEditingId(null);
        processingRef.current = false;
        setProcessing(false);

        setStatus(
          `${data.message || "Transcription saved"} · Record #${data.id}`
        );

        await loadHistory();
        socket.disconnect();

        if (socketRef.current === socket) {
          socketRef.current = null;
        }
      });

      socket.on("transcription_error", async (data) => {
        setStatus(data.error || "Transcription failed.");
        await finishRecording();
        processingRef.current = false;
        setProcessing(false);
      });

      socket.on("disconnect", () => {
        if (stoppingRef.current || processingRef.current) {
          processingRef.current = false;
          stoppingRef.current = false;
          setProcessing(false);
          setStatus("Server connection lost while saving. Please try again.");
        } else if (recordingRef.current) {
          setStatus("WebSocket disconnected. Please try again.");
        }
      });
    });
  }, [finishRecording, loadHistory]);

  async function startRecording() {
    if (recordingRef.current || processingRef.current) return;

    if (!navigator.mediaDevices?.getUserMedia) {
      setStatus("Microphone access requires localhost or HTTPS.");
      return;
    }

    let socket;

    try {
      setStatus("Requesting microphone permission...");

      const stream = await navigator.mediaDevices.getUserMedia({
        audio: {
          channelCount: 1,
          echoCancellation: true,
          noiseSuppression: true,
          autoGainControl: true,
        },
      });

      streamRef.current = stream;

      const AudioContextClass =
        window.AudioContext || window.webkitAudioContext;

      if (!AudioContextClass) {
        throw new Error("Web Audio API is not supported.");
      }

      const audioContext = new AudioContextClass();
      audioContextRef.current = audioContext;

      await audioContext.resume();

      if (audioContext.sampleRate < TARGET_SAMPLE_RATE) {
        throw new Error(
          `Microphone sample rate ${audioContext.sampleRate} Hz is too low.`
        );
      }

      socket = await createSocket();

      socket.emit("audio_start", {
        language: languageMap[language] || "auto",
      });

      const source = audioContext.createMediaStreamSource(stream);
      sourceRef.current = source;

      const processor = audioContext.createScriptProcessor(4096, 1, 1);
      processorRef.current = processor;

      const muteGain = audioContext.createGain();
      muteGain.gain.value = 0;
      muteGainRef.current = muteGain;

      processor.onaudioprocess = (event) => {
        const activeSocket = socketRef.current;

        if (
          !recordingRef.current ||
          stoppingRef.current ||
          !activeSocket?.connected
        ) {
          return;
        }

        const input = event.inputBuffer.getChannelData(0);
        const pcm = downsampleToPCM16(input, audioContext.sampleRate);

        activeSocket.emit("audio_chunk", pcm.buffer);
      };

      source.connect(processor);
      processor.connect(muteGain);
      muteGain.connect(audioContext.destination);

      recordingRef.current = true;
      stoppingRef.current = false;
      processingRef.current = false;

      setRecording(true);
      setProcessing(false);
      setTranscript("");
      savedTextRef.current = "";
      setEditingId(null);
      setStatus("Recording started. Speak naturally.");
    } catch (error) {
      recordingRef.current = false;
      processingRef.current = false;

      setRecording(false);
      setProcessing(false);

      await releaseAudio();

      const activeSocket = socketRef.current || socket;

      if (activeSocket) {
        activeSocket.disconnect();
      }

      socketRef.current = null;
      setStatus(error.message || "Could not start recording.");
    }
  }

  async function stopRecording() {
    if (!recordingRef.current || stoppingRef.current) return;

    stoppingRef.current = true;
    processingRef.current = true;

    setProcessing(true);
    setStatus("Finishing audio and saving the final transcript...");

    if (processorRef.current) {
      processorRef.current.onaudioprocess = null;
    }

    await releaseAudio();

    recordingRef.current = false;
    setRecording(false);

    const socket = socketRef.current;

    if (!socket?.connected) {
      stoppingRef.current = false;
      processingRef.current = false;
      setProcessing(false);
      setStatus("Connection lost before final transcription.");
      return;
    }

    socket.emit("audio_stop");

    window.setTimeout(() => {
      if (processingRef.current && stoppingRef.current) {
        processingRef.current = false;
        stoppingRef.current = false;
        setProcessing(false);
        setStatus(
          "Timed out waiting for the transcript. Try a shorter recording."
        );
      }
    }, 90000);
  }

  async function saveTranscript() {
    if (!transcript.trim()) {
      setStatus("Please record or enter some text first.");
      return;
    }

    if (processingRef.current) return;

    const isEditing = editingId !== null;
    const url = isEditing
      ? `${API}/transcriptions/${editingId}`
      : `${API}/transcriptions`;

    try {
      processingRef.current = true;
      setProcessing(true);

      const response = await fetch(url, {
        method: isEditing ? "PUT" : "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          transcript_text: transcript.trim(),
          language: languageMap[language] || "auto",
        }),
      });

      const data = await response.json();

      if (!response.ok) {
        throw new Error(data.error || "Save failed.");
      }

      setTranscript("");
      savedTextRef.current = "";
      setEditingId(null);
      setStatus(isEditing ? "Transcription updated!" : "Text saved!");

      await loadHistory();
    } catch (error) {
      setStatus(error.message || "Could not save text.");
    } finally {
      processingRef.current = false;
      setProcessing(false);
    }
  }

  function editTranscript(item) {
    if (recordingRef.current || processingRef.current) return;

    setTranscript(item.transcript_text || "");
    savedTextRef.current = item.transcript_text || "";

    const lang = (item.language || "en").toLowerCase();
    const matching = Object.entries(languageMap).find(
      ([, code]) => code === lang
    );

    setLanguage(matching?.[0] || "en-IN");
    setEditingId(item.id);
    setStatus(`Editing transcription #${item.id}.`);
  }

  function cancelEdit() {
    setTranscript("");
    savedTextRef.current = "";
    setEditingId(null);
    setStatus("Edit cancelled.");
  }

  async function deleteTranscript(id) {
    if (recordingRef.current || processingRef.current) return;

    if (
      !window.confirm(
        "Are you sure you want to delete this transcription?"
      )
    ) {
      return;
    }

    try {
      processingRef.current = true;
      setProcessing(true);

      const response = await fetch(`${API}/transcriptions/${id}`, {
        method: "DELETE",
      });

      const data = await response.json();

      if (!response.ok) {
        throw new Error(data.error || "Delete failed.");
      }

      if (editingId === id) {
        cancelEdit();
      }

      setStatus("Transcription deleted.");
      await loadHistory();
    } catch (error) {
      setStatus(error.message || "Could not delete transcription.");
    } finally {
      processingRef.current = false;
      setProcessing(false);
    }
  }

  useEffect(() => {
    mountedRef.current = true;

    return () => {
      mountedRef.current = false;
      recordingRef.current = false;
      stoppingRef.current = true;

      if (socketRef.current) {
        socketRef.current.disconnect();
        socketRef.current = null;
      }

      if (processorRef.current) {
        processorRef.current.onaudioprocess = null;
      }

      if (streamRef.current) {
        streamRef.current.getTracks().forEach((track) => track.stop());
      }

      if (
        audioContextRef.current &&
        audioContextRef.current.state !== "closed"
      ) {
        audioContextRef.current.close().catch(() => {});
      }
    };
  }, []);

  return (
    <main className="app">
      <header>
        <div className="brand">
          Speak<span>Flow</span>
        </div>
        <div className="badge">AI SPEECH WORKSPACE</div>
      </header>

      <section className="hero">
        <p className="eyebrow">STREAMING SPEECH RECOGNITION</p>
        <h1>
          Your voice, <span>in text.</span>
        </h1>
        <p className="subtitle">
          Stream microphone audio to your own Faster-Whisper backend.
          Review and manage your saved transcripts in MySQL.
        </p>
      </section>

      <section className="workspace">
        <div className="panel">
          <div className="panel-title">
            <div>
              <h2>
                {editingId !== null
                  ? `Edit transcription #${editingId}`
                  : "Live transcription"}
              </h2>
              <p>Allow microphone access when prompted.</p>
            </div>

            <span className={recording ? "live active" : "live"}>
              {recording ? "● LIVE" : "● READY"}
            </span>
          </div>

          <label htmlFor="language">Recognition language</label>
          <select
            id="language"
            value={language}
            onChange={(event) => setLanguage(event.target.value)}
            disabled={recording || processing}
          >
            <option value="en-IN">English (India)</option>
            <option value="hi-IN">Hindi</option>
            <option value="ta-IN">Tamil</option>
            <option value="en-US">English (US)</option>
          </select>

          <textarea
            value={transcript}
            onChange={(event) => setTranscript(event.target.value)}
            placeholder="Live transcript updates will appear here..."
            rows={9}
            disabled={recording || processing}
          />

          <div className="controls">
            {!recording ? (
              <button
                className="primary"
                onClick={startRecording}
                disabled={processing || loading || editingId !== null}
              >
                <Mic size={18} />
                Start recording
              </button>
            ) : (
              <button
                className="stop"
                onClick={stopRecording}
                disabled={processing}
              >
                <Square size={16} />
                Stop and save
              </button>
            )}

            <button
              className="secondary"
              onClick={saveTranscript}
              disabled={recording || processing || !transcript.trim()}
            >
              <Save size={18} />
              {editingId !== null ? "Update transcript" : "Save text"}
            </button>

            {editingId !== null && (
              <button
                className="secondary"
                onClick={cancelEdit}
                disabled={processing}
              >
                <X size={16} />
                Cancel edit
              </button>
            )}
          </div>

          <p className="status" role="status">
            {processing && <LoaderCircle size={16} />}
            {status}
          </p>

          <p className="hint">
            <Radio size={14} /> Audio chunks are sent over Socket.IO.
            Interim text may be revised by the model. The final transcript
            is saved to MySQL when recording stops.
          </p>
        </div>

        <div className="panel history-panel">
          <div className="panel-title">
            <div>
              <h2>Transcription history</h2>
              <p>Your saved records from MySQL</p>
            </div>

            <button
              className="icon-button"
              onClick={loadHistory}
              disabled={loading}
              title="Refresh history"
            >
              <RefreshCw size={18} />
            </button>
          </div>

          <div className="history-count">
            {history.length} saved{" "}
            {history.length === 1 ? "record" : "records"}
          </div>

          {loading && history.length === 0 ? (
            <div className="empty">
              <p>Loading transcription history...</p>
            </div>
          ) : history.length === 0 ? (
            <div className="empty">
              <Mic size={30} />
              <p>No transcripts yet</p>
              <span>Record and save your first transcript.</span>
            </div>
          ) : (
            <div className="history-list">
              {history.map((item) => (
                <article className="history-item" key={item.id}>
                  <div className="history-meta">
                    <span>TRANSCRIPT #{item.id}</span>
                    <span>{item.language || "auto"}</span>
                  </div>

                  <p>{item.transcript_text}</p>

                  {item.created_at && (
                    <p className="hint">
                      Created:{" "}
                      {new Date(item.created_at).toLocaleString()}
                    </p>
                  )}

                  <div className="history-actions">
                    <button
                      className="secondary small"
                      onClick={() => editTranscript(item)}
                      disabled={recording || processing}
                    >
                      Edit text
                    </button>

                    <button
                      className="delete small"
                      onClick={() => deleteTranscript(item.id)}
                      disabled={recording || processing}
                    >
                      <Trash2 size={14} />
                      Delete
                    </button>
                  </div>
                </article>
              ))}
            </div>
          )}
        </div>
      </section>

      <footer>
        SpeakFlow · Procucev AI Tech Hiring Assignment
      </footer>
    </main>
  );
}
