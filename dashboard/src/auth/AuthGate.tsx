import { ReactNode, useState } from "react";
import { getToken } from "../api/client";
import PinScreen from "./PinScreen";

export default function AuthGate({ children }: { children: ReactNode }) {
  const [authed, setAuthed] = useState<boolean>(() => !!getToken());
  if (!authed) return <PinScreen onAuthed={() => setAuthed(true)} />;
  return <>{children}</>;
}
