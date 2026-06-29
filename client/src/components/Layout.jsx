import {NavLink, Outlet} from "react-router-dom";
import {useAuth} from "../auth/AuthContext";
import {normalizeRole} from "../utils/roles";

export function Layout() {
  const {user, logout} = useAuth();

  return (
    <div className="app-shell">
      <aside className="sidebar">
        <div className="brand">
          <div className="brand-mark">AI</div>
          <div>
            <p className="eyebrow">Cloud SQL Studio</p>
            <h1>AI SQL Query Generator</h1>
          </div>
        </div>
        <nav className="nav-list">
          <NavLink to="/">Overview</NavLink>
          <NavLink to="/connections">Data Sources</NavLink>
          <NavLink to="/query">Query Studio</NavLink>
          <NavLink to="/history">Query History</NavLink>
          <NavLink to="/admin/audit-logs">Security Audit</NavLink>
        </nav>
        <div className="account-card">
          <small>Signed in as</small>
          <strong>{user?.username}</strong>
          <span>{normalizeRole(user?.role)}</span>
          <button type="button" className="secondary" onClick={logout}>Logout</button>
        </div>
      </aside>
      <main className="workspace">
        <Outlet />
      </main>
    </div>
  );
}
