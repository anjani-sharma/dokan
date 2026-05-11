import { NavLink } from "react-router-dom";
import { clearToken } from "../api/client";
import {
  IconBox, IconBuilding, IconCart, IconChart, IconDashboard, IconFile,
  IconLogout, IconPackage, IconUsers,
} from "./Icons";

// Configurable shop label shown under the logo. Hardcoded for now —
// could later read from a backend /config endpoint or build-time env var.
const SHOP_LABEL = "RK ENTERPRISES";

const links = [
  { to: "/",           label: "Dashboard",  icon: IconDashboard },
  { to: "/sales",      label: "Sales",      icon: IconCart },
  { to: "/invoices",   label: "Purchases",  icon: IconPackage },
  { to: "/customers",  label: "Customers",  icon: IconUsers },
  { to: "/stock",      label: "Products",   icon: IconBox },
  { to: "/payments",   label: "Payments",   icon: IconFile },
  { to: "/analytics",  label: "Analytics",  icon: IconChart },
  { to: "/suppliers",  label: "Vendors",    icon: IconBuilding },
];

export default function Sidebar({ onLinkClick }: { onLinkClick?: () => void }) {
  const logout = () => {
    clearToken();
    window.location.reload();
  };
  return (
    <aside className="sidebar">
      <div className="sidebar-brand">
        <img src="/dokane-logo.png" alt="DOKANE" className="sidebar-logo" />
        <div className="sidebar-shop-name">{SHOP_LABEL}</div>
      </div>

      <nav className="sidebar-nav">
        {links.map(({ to, label, icon: Icon }) => (
          <NavLink
            key={to}
            to={to}
            end={to === "/"}
            onClick={onLinkClick}
            className={({ isActive }) => "sidebar-link" + (isActive ? " active" : "")}
          >
            <Icon className="icon" />
            {label}
          </NavLink>
        ))}
      </nav>

      <div className="sidebar-tg-note">
        <div className="label">Also available on Telegram</div>
        <div>Send voice or invoice photos</div>
      </div>

      <button
        className="sidebar-link"
        onClick={logout}
        style={{ border: "none", background: "transparent", cursor: "pointer", width: "100%", textAlign: "left" }}
      >
        <IconLogout className="icon" />
        Sign out
      </button>

      <div className="sidebar-footer">
        <img src="/ai-transformer.png" alt="AI Transformer" />
        <div className="col">
          <span className="by">Powered by</span>
          <span className="name">AI Transformers LTD</span>
        </div>
      </div>
    </aside>
  );
}
