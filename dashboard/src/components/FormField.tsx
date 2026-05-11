import { ReactNode } from "react";

interface FormFieldProps {
  label: string;
  hint?: string;
  error?: string;
  children: ReactNode;
}

export default function FormField({ label, hint, error, children }: FormFieldProps) {
  return (
    <div className="form-field">
      <label className="form-label">
        {label}
        {hint && <span className="form-label-hint">({hint})</span>}
      </label>
      {children}
      {error && <div className="form-error">{error}</div>}
    </div>
  );
}
