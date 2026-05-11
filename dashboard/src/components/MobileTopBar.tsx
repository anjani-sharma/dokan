import { useEffect, useState } from "react";
import Sidebar from "./Sidebar";
import { IconMenu, IconClose } from "./Icons";

export default function MobileTopBar() {
  const [open, setOpen] = useState(false);

  // Close drawer when navigating
  useEffect(() => {
    if (!open) return;
    const close = () => setOpen(false);
    window.addEventListener("popstate", close);
    return () => window.removeEventListener("popstate", close);
  }, [open]);

  // Lock body scroll while drawer open
  useEffect(() => {
    if (!open) return;
    const prev = document.body.style.overflow;
    document.body.style.overflow = "hidden";
    return () => { document.body.style.overflow = prev; };
  }, [open]);

  return (
    <>
      <div className="mobile-topbar">
        <button
          className="mobile-topbar-btn"
          aria-label="Open menu"
          onClick={() => setOpen(true)}
        >
          <IconMenu size={22} />
        </button>
        <div className="mobile-topbar-title">
          <img src="/dokane-logo.png" alt="" />
          DOKANE
        </div>
        <div style={{ width: 40 }} />
      </div>

      {open && (
        <>
          <div className="mobile-drawer-backdrop" onClick={() => setOpen(false)} />
          <div className="mobile-drawer">
            <div style={{ display: "flex", justifyContent: "flex-end", padding: "8px 8px 0" }}>
              <button
                className="mobile-topbar-btn"
                aria-label="Close menu"
                onClick={() => setOpen(false)}
              >
                <IconClose size={20} />
              </button>
            </div>
            <Sidebar onLinkClick={() => setOpen(false)} />
          </div>
        </>
      )}
    </>
  );
}
