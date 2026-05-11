import { useEffect, useRef, useState } from "react";
import Modal from "./Modal";
import { processVoice, VoiceProcessResult } from "../api/client";

interface Props {
  open: boolean;
  onClose: () => void;
  onResult: (r: VoiceProcessResult) => void;
}

// Captures microphone audio via MediaRecorder, uploads to /voice/process, and
// hands the classified intent back to the caller. The recording auto-stops
// after 30s as a safety so a forgotten-open mic doesn't blow through quota.

const MAX_SECONDS = 30;

export default function VoiceRecorderModal({ open, onClose, onResult }: Props) {
  const [state, setState] = useState<"idle" | "recording" | "uploading">("idle");
  const [elapsed, setElapsed] = useState(0);
  const [error, setError] = useState<string | null>(null);
  const recorderRef = useRef<MediaRecorder | null>(null);
  const chunksRef = useRef<BlobPart[]>([]);
  const streamRef = useRef<MediaStream | null>(null);
  const timerRef = useRef<number | null>(null);

  const cleanup = () => {
    if (timerRef.current != null) { window.clearInterval(timerRef.current); timerRef.current = null; }
    if (recorderRef.current && recorderRef.current.state !== "inactive") {
      try { recorderRef.current.stop(); } catch { /* noop */ }
    }
    if (streamRef.current) streamRef.current.getTracks().forEach((t) => t.stop());
    streamRef.current = null;
    recorderRef.current = null;
  };

  useEffect(() => {
    if (!open) {
      cleanup();
      setState("idle");
      setElapsed(0);
      setError(null);
      chunksRef.current = [];
    }
  }, [open]);

  const start = async () => {
    setError(null);
    chunksRef.current = [];
    try {
      const stream = await navigator.mediaDevices.getUserMedia({ audio: true });
      streamRef.current = stream;
      // Browsers pick what they can encode — webm/opus on Chromium,
      // mp4 on Safari. Whisper handles either, so don't constrain.
      const rec = new MediaRecorder(stream);
      recorderRef.current = rec;
      rec.ondataavailable = (e) => { if (e.data.size > 0) chunksRef.current.push(e.data); };
      rec.onstop = onRecorderStop;
      rec.start();
      setState("recording");
      setElapsed(0);
      timerRef.current = window.setInterval(() => {
        setElapsed((s) => {
          if (s + 1 >= MAX_SECONDS) stop();
          return s + 1;
        });
      }, 1000);
    } catch (e) {
      setError(e instanceof Error ? e.message : "Mic access denied");
    }
  };

  const stop = () => {
    if (recorderRef.current && recorderRef.current.state === "recording") {
      recorderRef.current.stop();
    }
  };

  const onRecorderStop = async () => {
    if (timerRef.current != null) { window.clearInterval(timerRef.current); timerRef.current = null; }
    if (streamRef.current) streamRef.current.getTracks().forEach((t) => t.stop());
    streamRef.current = null;

    const mime = recorderRef.current?.mimeType ?? "audio/webm";
    const blob = new Blob(chunksRef.current, { type: mime });
    if (blob.size < 200) {
      setError("Recording was too short. Try again.");
      setState("idle");
      return;
    }
    const ext = mime.includes("mp4") ? "mp4" : mime.includes("ogg") ? "ogg" : "webm";

    setState("uploading");
    try {
      const result = await processVoice(blob, ext);
      onResult(result);
    } catch (e) {
      const msg = (e as { response?: { data?: { detail?: string } } })?.response?.data?.detail;
      setError(msg ?? "Could not process audio.");
      setState("idle");
    }
  };

  return (
    <Modal open={open} onClose={onClose} title="Speak the entry">
      <div className="form-grid" style={{ alignItems: "center", textAlign: "center" }}>
        <div style={{
          width: 96, height: 96, borderRadius: "50%", margin: "0 auto",
          background: state === "recording" ? "var(--red-soft)" : "var(--surface-elev)",
          display: "flex", alignItems: "center", justifyContent: "center",
          fontSize: 40, transition: "background .2s",
        }}>
          {state === "uploading" ? "⏳" : "🎤"}
        </div>

        {state === "idle" && !error && (
          <div className="text-muted" style={{ fontSize: 13 }}>
            Try: "Sold 5 wires to Rajesh for 250 each" or "Received 1200 via GPay from Rajesh".
          </div>
        )}

        {state === "recording" && (
          <div className="bold" style={{ fontSize: 16 }}>
            Recording… {elapsed}s
          </div>
        )}

        {state === "uploading" && (
          <div className="text-muted">Transcribing…</div>
        )}

        {error && <div className="form-error">{error}</div>}

        <div className="form-actions" style={{ justifyContent: "center" }}>
          {state === "idle" && (
            <>
              <button type="button" className="btn btn-ghost" onClick={onClose}>Cancel</button>
              <button type="button" className="btn btn-primary" onClick={start}>Start recording</button>
            </>
          )}
          {state === "recording" && (
            <button type="button" className="btn btn-primary" onClick={stop}>Stop</button>
          )}
        </div>
      </div>
    </Modal>
  );
}
