import { ReactNode, useCallback, useEffect, useState } from "react";
import { Toast, ToastContext } from "../hooks/useToast";

let _id = 0;

export function ToastProvider({ children }: { children: ReactNode }) {
  const [toasts, setToasts] = useState<Toast[]>([]);

  const dismiss = useCallback((id: number) => {
    setToasts((prev) => prev.filter((t) => t.id !== id));
  }, []);

  const push = useCallback((t: Omit<Toast, "id">) => {
    const id = ++_id;
    setToasts((prev) => [...prev, { ...t, id }]);
    setTimeout(() => dismiss(id), 4000);
  }, [dismiss]);

  return (
    <ToastContext.Provider value={{ toasts, push, dismiss }}>
      {children}
      <ToastStack toasts={toasts} dismiss={dismiss} />
    </ToastContext.Provider>
  );
}

function ToastStack({ toasts, dismiss }: { toasts: Toast[]; dismiss: (id: number) => void }) {
  return (
    <div className="toast-stack">
      {toasts.map((t) => (
        <div
          key={t.id}
          className={"toast toast-" + t.kind}
          onClick={() => dismiss(t.id)}
          role="status"
        >
          <div className="toast-title">{t.title}</div>
          {t.body && <div className="toast-body">{t.body}</div>}
        </div>
      ))}
    </div>
  );
}
