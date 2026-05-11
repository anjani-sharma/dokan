import { useEffect, useRef, useState } from "react";
import { login, setToken } from "../api/client";

interface PinScreenProps {
  onAuthed: () => void;
}

const PIN_LEN = 4;

export default function PinScreen({ onAuthed }: PinScreenProps) {
  const [digits, setDigits] = useState<string[]>(() => Array(PIN_LEN).fill(""));
  const [error, setError] = useState<string | null>(null);
  const [submitting, setSubmitting] = useState(false);
  const inputs = useRef<(HTMLInputElement | null)[]>([]);

  useEffect(() => { inputs.current[0]?.focus(); }, []);

  const setAt = (i: number, v: string) => {
    setError(null);
    const cleaned = v.replace(/\D/g, "").slice(0, 1);
    setDigits((prev) => {
      const next = [...prev];
      next[i] = cleaned;
      return next;
    });
    if (cleaned && i < PIN_LEN - 1) inputs.current[i + 1]?.focus();
  };

  const onKey = (i: number, e: React.KeyboardEvent<HTMLInputElement>) => {
    if (e.key === "Backspace" && !digits[i] && i > 0) inputs.current[i - 1]?.focus();
  };

  const onPaste = (e: React.ClipboardEvent<HTMLInputElement>) => {
    const text = e.clipboardData.getData("text").replace(/\D/g, "").slice(0, PIN_LEN);
    if (!text) return;
    e.preventDefault();
    const next = Array(PIN_LEN).fill("").map((_, i) => text[i] ?? "");
    setDigits(next);
    const focusAt = Math.min(text.length, PIN_LEN - 1);
    inputs.current[focusAt]?.focus();
  };

  // Auto-submit when all digits are filled.
  useEffect(() => {
    if (digits.every((d) => d) && !submitting) {
      void submit();
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [digits]);

  const submit = async () => {
    setSubmitting(true);
    setError(null);
    try {
      const { token } = await login(digits.join(""));
      setToken(token);
      onAuthed();
    } catch {
      setError("Incorrect PIN");
      setDigits(Array(PIN_LEN).fill(""));
      inputs.current[0]?.focus();
    } finally {
      setSubmitting(false);
    }
  };

  return (
    <div className="pin-screen">
      <div className="pin-card">
        <img src="/dokane-logo.png" alt="DOKANE" className="pin-logo" />
        <div className="pin-title">DOKANE</div>
        <div className="pin-subtitle">Enter your 4-digit PIN to continue</div>
        <div className="pin-boxes" onPaste={onPaste}>
          {digits.map((d, i) => (
            <input
              key={i}
              ref={(el) => { inputs.current[i] = el; }}
              className={"pin-box" + (error ? " error" : "")}
              inputMode="numeric"
              autoComplete="one-time-code"
              maxLength={1}
              value={d}
              onChange={(e) => setAt(i, e.target.value)}
              onKeyDown={(e) => onKey(i, e)}
              disabled={submitting}
            />
          ))}
        </div>
        {error && <div className="pin-error-msg">{error}</div>}
        <div className="pin-footer">
          <img src="/ai-transformer.png" alt="" />
          Product of AI Transformer
        </div>
      </div>
    </div>
  );
}
