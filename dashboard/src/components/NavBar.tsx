import { NavLink } from "react-router-dom";
import { clearToken } from "../api/client";

const links = [
  { to: "/",           label: "Overview" },
  { to: "/sales",      label: "Sales" },
  { to: "/customers",  label: "Customers" },
  { to: "/suppliers",  label: "Suppliers" },
  { to: "/invoices",   label: "Invoices" },
  { to: "/stock",      label: "Stock" },
  { to: "/payments",   label: "Payments" },
];

export default function NavBar() {
  const logout = () => {
    clearToken();
    window.location.reload();
  };

  return (
    <nav className="navbar">
      <div className="navbar-brand">
        <img src="/dokane-logo.png" alt="DOKANE" className="brand-logo" />
        <span className="brand-name">DOKANE</span>
      </div>
      <div className="navbar-links">
        {links.map(({ to, label }) => (
          <NavLink
            key={to}
            to={to}
            end={to === "/"}
            className={({ isActive }) => "nav-link" + (isActive ? " active" : "")}
          >
            {label}
          </NavLink>
        ))}
      </div>
      <button className="btn btn-ghost nav-logout" onClick={logout} title="Sign out">
        Sign out
      </button>
    </nav>
  );
}
