import { BrowserRouter, Routes, Route, Navigate } from "react-router-dom";
import MobileTopBar from "./components/MobileTopBar";
import QuickAddFab from "./components/QuickAddFab";
import Sidebar from "./components/Sidebar";
import Analytics from "./pages/Analytics";
import Customers from "./pages/Customers";
import Dashboard from "./pages/Dashboard";
import Invoices from "./pages/Invoices";
import Payments from "./pages/Payments";
import Sales from "./pages/Sales";
import Stock from "./pages/Stock";
import Suppliers from "./pages/Suppliers";
import AuthGate from "./auth/AuthGate";
import { ToastProvider } from "./components/Toast";

export default function App() {
  return (
    <ToastProvider>
      <AuthGate>
        <BrowserRouter>
          <div className="app">
            <Sidebar />
            <div>
              <MobileTopBar />
              <main className="main-content">
                <Routes>
                  <Route path="/"           element={<Dashboard />} />
                  <Route path="/sales"      element={<Sales />} />
                  <Route path="/customers"  element={<Customers />} />
                  <Route path="/suppliers"  element={<Suppliers />} />
                  <Route path="/invoices"   element={<Invoices />} />
                  <Route path="/stock"      element={<Stock />} />
                  <Route path="/payments"   element={<Payments />} />
                  <Route path="/analytics"  element={<Analytics />} />
                  <Route path="*"           element={<Navigate to="/" replace />} />
                </Routes>
              </main>
              <QuickAddFab />
            </div>
          </div>
        </BrowserRouter>
      </AuthGate>
    </ToastProvider>
  );
}
