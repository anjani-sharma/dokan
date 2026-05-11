import { BrowserRouter, Routes, Route, Navigate } from "react-router-dom";
import NavBar from "./components/NavBar";
import Footer from "./components/Footer";
import Dashboard from "./pages/Dashboard";
import Sales from "./pages/Sales";
import Customers from "./pages/Customers";
import Suppliers from "./pages/Suppliers";
import Invoices from "./pages/Invoices";
import Stock from "./pages/Stock";
import Payments from "./pages/Payments";
import AuthGate from "./auth/AuthGate";
import { ToastProvider } from "./components/Toast";

export default function App() {
  return (
    <ToastProvider>
      <AuthGate>
        <BrowserRouter>
          <div className="app">
            <NavBar />
            <main className="main-content">
              <Routes>
                <Route path="/"           element={<Dashboard />} />
                <Route path="/sales"      element={<Sales />} />
                <Route path="/customers"  element={<Customers />} />
                <Route path="/suppliers"  element={<Suppliers />} />
                <Route path="/invoices"   element={<Invoices />} />
                <Route path="/stock"      element={<Stock />} />
                <Route path="/payments"   element={<Payments />} />
                <Route path="*"           element={<Navigate to="/" replace />} />
              </Routes>
            </main>
            <Footer />
          </div>
        </BrowserRouter>
      </AuthGate>
    </ToastProvider>
  );
}
