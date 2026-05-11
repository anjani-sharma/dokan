import { useEffect, useRef, useState } from "react";
import { VoiceProcessResult } from "../api/client";
import { IconCart, IconFile, IconMic, IconPlus, IconUser, IconPackage } from "./Icons";
import Modal from "./Modal";
import SaleForm from "./SaleForm";
import InvoiceForm from "./InvoiceForm";
import PaymentForm from "./PaymentForm";
import VoiceRecorderModal from "./VoiceRecorderModal";

type ModalKind = "sale" | "payment" | "invoice" | "voice" | null;

interface Props {
  /** Called after any successful save so the surrounding page can refresh. */
  onSaved?: () => void;
}

export default function QuickAddFab({ onSaved }: Props) {
  const [menuOpen, setMenuOpen] = useState(false);
  const [modal, setModal] = useState<ModalKind>(null);
  // When voice classification produces an actionable intent, we pre-fill the
  // matching form via these defaults. Null = open the form with no prefill.
  const [voicePrefill, setVoicePrefill] = useState<VoiceProcessResult | null>(null);
  const [pendingForm, setPendingForm] = useState<"sale" | "payment-in" | "payment-out" | null>(null);
  const menuRef = useRef<HTMLDivElement | null>(null);

  useEffect(() => {
    if (!menuOpen) return;
    const handler = (e: MouseEvent) => {
      if (menuRef.current && !menuRef.current.contains(e.target as Node)) {
        setMenuOpen(false);
      }
    };
    document.addEventListener("mousedown", handler);
    return () => document.removeEventListener("mousedown", handler);
  }, [menuOpen]);

  const open = (kind: ModalKind) => {
    setMenuOpen(false);
    setVoicePrefill(null);
    setPendingForm(null);
    setModal(kind);
  };
  const close = () => {
    setModal(null);
    setVoicePrefill(null);
    setPendingForm(null);
  };
  const saved = () => {
    setModal(null);
    setVoicePrefill(null);
    setPendingForm(null);
    window.dispatchEvent(new CustomEvent("ananta:data-changed"));
    onSaved?.();
  };

  const handleVoiceResult = (r: VoiceProcessResult) => {
    setVoicePrefill(r);
    if (r.intent === "sale") {
      setPendingForm("sale");
      setModal("sale");
    } else if (r.intent === "payment_in") {
      setPendingForm("payment-in");
      setModal("payment");
    } else if (r.intent === "payment_out") {
      setPendingForm("payment-out");
      setModal("payment");
    } else {
      // Unknown — stay on the voice modal but show a chooser; user picks the form.
      setPendingForm(null);
      // Modal stays open as "voice" so the chooser UI in the recorder shows.
    }
  };

  // Build prefill props from voice intent
  const saleDefaults = voicePrefill?.sale
    ? {
        product_name: voicePrefill.sale.product_name,
        qty: voicePrefill.sale.qty,
        selling_price: voicePrefill.sale.selling_price,
        customer_name: voicePrefill.sale.customer_name,
      }
    : undefined;
  const paymentDefaults = voicePrefill?.payment
    ? {
        amount: voicePrefill.payment.amount,
        payment_mode: voicePrefill.payment.payment_mode,
        vendor_name: voicePrefill.payment.vendor_name,
        customer_name: voicePrefill.payment.customer_name,
      }
    : undefined;

  return (
    <>
      {menuOpen && (
        <div className="fab-menu" ref={menuRef}>
          <button className="fab-menu-item" onClick={() => open("voice")}>
            <span className="dot" style={{ background: "var(--brand)" }} />
            <IconMic size={16} /> Voice entry
          </button>
          <button className="fab-menu-item" onClick={() => open("sale")}>
            <span className="dot" style={{ background: "var(--green)" }} />
            <IconCart size={16} /> New sale
          </button>
          <button className="fab-menu-item" onClick={() => open("payment")}>
            <span className="dot" style={{ background: "var(--blue)" }} />
            <IconFile size={16} /> New payment
          </button>
          <button className="fab-menu-item" onClick={() => open("invoice")}>
            <span className="dot" style={{ background: "var(--purple)" }} />
            <IconPackage size={16} /> New purchase
          </button>
        </div>
      )}

      <button
        className="fab"
        aria-label="Quick add"
        onClick={() => setMenuOpen((v) => !v)}
      >
        {menuOpen ? <IconPlus size={22} style={{ transform: "rotate(45deg)" }} /> : <IconPlus size={22} />}
      </button>

      <VoiceRecorderModal
        open={modal === "voice"}
        onClose={close}
        onResult={handleVoiceResult}
      />

      <Modal open={modal === "sale"} onClose={close} title="Record a sale">
        <SaleForm onCancel={close} onSaved={saved} defaults={saleDefaults} />
      </Modal>
      <Modal open={modal === "payment"} onClose={close} title="Record a payment">
        <PaymentForm
          onCancel={close}
          onSaved={saved}
          defaultDirection={pendingForm === "payment-in" ? "inflow" : pendingForm === "payment-out" ? "outflow" : undefined}
          defaults={paymentDefaults}
        />
      </Modal>
      <Modal open={modal === "invoice"} onClose={close} title="Record a purchase invoice" wide>
        <InvoiceForm onCancel={close} onSaved={saved} />
      </Modal>

      {/* Bump the unused-icon import — kept around for future menu items. */}
      <span style={{ display: "none" }}><IconUser /></span>
    </>
  );
}
