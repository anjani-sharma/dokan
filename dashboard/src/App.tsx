import { BrowserRouter, Routes, Route, Navigate } from "react-router-dom";
import NavBar from "./components/NavBar";
import Dashboard from "./pages/Dashboard";
import Invoices from "./pages/Invoices";
import Stock from "./pages/Stock";
import Payments from "./pages/Payments";

export default function App() {
  return (
    <BrowserRouter>
      <div className="app">
        <NavBar />
        <main className="main-content">
          <Routes>
            <Route path="/"          element={<Dashboard />} />
            <Route path="/invoices"  element={<Invoices />} />
            <Route path="/stock"     element={<Stock />} />
            <Route path="/payments"  element={<Payments />} />
            <Route path="*"          element={<Navigate to="/" replace />} />
          </Routes>
        </main>
      </div>
    </BrowserRouter>
  );
}
