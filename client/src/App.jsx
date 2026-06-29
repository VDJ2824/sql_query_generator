import {BrowserRouter, Route, Routes} from "react-router-dom";
import {AuthProvider} from "./auth/AuthContext";
import {Layout} from "./components/Layout";
import {ProtectedRoute} from "./components/ProtectedRoute";
import {AdminAuditLogs} from "./pages/AdminAuditLogs";
import {Dashboard} from "./pages/Dashboard";
import {DatabaseConnections} from "./pages/DatabaseConnections";
import {History} from "./pages/History";
import {Login} from "./pages/Login";
import {QueryWorkspace} from "./pages/QueryWorkspace";

export default function App() {
  return (
    <AuthProvider>
      <BrowserRouter>
        <Routes>
          <Route path="/login" element={<Login />} />
          <Route
            path="/"
            element={
              <ProtectedRoute>
                <Layout />
              </ProtectedRoute>
            }
          >
            <Route index element={<Dashboard />} />
            <Route path="connections" element={<DatabaseConnections />} />
            <Route path="query" element={<QueryWorkspace />} />
            <Route path="history" element={<History />} />
            <Route path="admin/audit-logs" element={<AdminAuditLogs />} />
          </Route>
        </Routes>
      </BrowserRouter>
    </AuthProvider>
  );
}
