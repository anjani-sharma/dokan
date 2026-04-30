import { NavLink } from "react-router-dom";

const links = [
  { to: "/", label: "Overview" },
  { to: "/invoices", label: "Invoices" },
  { to: "/stock", label: "Stock" },
  { to: "/payments", label: "Payments" },
];

export default function NavBar() {
  return (
    <nav className="navbar">
      <div className="navbar-brand">⚡ Ananta</div>
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
    </nav>
  );
}
