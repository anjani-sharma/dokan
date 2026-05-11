import { useEffect, useRef, useState } from "react";
import { IconCart, IconFile, IconPlus, IconUser, IconPackage } from "./Icons";
import Modal from "./Modal";
import SaleForm from "./SaleForm";
import InvoiceForm from "./InvoiceForm";
import PaymentForm from "./PaymentForm";

type ModalKind = "sale" | "payment" | "invoice" | null;

interface Props {
  /** Called after any successful save so the surrounding page can refresh. */
  onSaved?: () => void;
}

export default function QuickAddFab({ onSaved }: Props) {
  const [menuOpen, setMenuOpen] = useState(false);
  const [modal, setModal] = useState<ModalKind>(null);
  const menuRef = useRef<HTMLDivElement | null>(null);

  // Close menu on outside click
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
    setModal(kind);
  };
  const close = () => setModal(null);
  const saved = () => {
    setModal(null);
    // Broadcast so any open page can refetch without us holding a ref to it.
    window.dispatchEvent(new CustomEvent("ananta:data-changed"));
    onSaved?.();
  };

  return (
    <>
      {menuOpen && (
        <div className="fab-menu" ref={menuRef}>
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

      <Modal open={modal === "sale"} onClose={close} title="Record a sale">
        <SaleForm onCancel={close} onSaved={saved} />
      </Modal>
      <Modal open={modal === "payment"} onClose={close} title="Record a payment">
        <PaymentForm onCancel={close} onSaved={saved} />
      </Modal>
      <Modal open={modal === "invoice"} onClose={close} title="Record a purchase invoice" wide>
        <InvoiceForm onCancel={close} onSaved={saved} />
      </Modal>

      {/* Bump the unused-icon import — kept around for future menu items. */}
      <span style={{ display: "none" }}><IconUser /></span>
    </>
  );
}
