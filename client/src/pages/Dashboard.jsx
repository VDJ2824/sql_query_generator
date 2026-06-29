import {useEffect, useState} from "react";
import {useAuth} from "../auth/AuthContext";
import {ApiClient} from "../services/ApiClient";
import {normalizeRole} from "../utils/roles";

function engineLabel(connection) {
  if (connection?.databaseType === "mysql") return "MySQL";
  if (connection?.databaseType === "postgresql") return "PostgreSQL";
  return connection?.databaseType || "SQL";
}

export function Dashboard() {
  const {user} = useAuth();
  const [connections, setConnections] = useState([]);
  const [history, setHistory] = useState([]);
  const [message, setMessage] = useState("");

  useEffect(() => {
    let active = true;
    async function loadDashboardData() {
      try {
        const [connectionResponse, historyResponse] = await Promise.all([
          ApiClient.listDatabaseConnections(),
          ApiClient.history(),
        ]);
        if (!active) return;
        setConnections(connectionResponse.databaseConnections || []);
        setHistory((historyResponse.history || []).slice(0, 5));
      } catch (error) {
        if (active) setMessage(error.message || "Could not load dashboard data.");
      }
    }
    loadDashboardData();
    return () => {
      active = false;
    };
  }, []);

  return (
    <section className="page-stack">
      <div className="hero-card">
        <p className="eyebrow">Workspace Overview</p>
        <h2>AI SQL Query Generator</h2>
        <p>
          Convert natural-language requests into validated SQL for your approved cloud databases.
          Your account keeps query history, selected options, workspace ownership, and audit records organized.
        </p>
      </div>

      {message && <p className="notice">{message}</p>}

      <div className="grid">
        <article className="panel">
          <h3>Account</h3>
          <p className="dashboard-value">{user.username}</p>
          <p className="muted">{user.email}</p>
        </article>
        <article className="panel">
          <h3>Role</h3>
          <p className="dashboard-value">{normalizeRole(user.role)}</p>
          <p className="muted">Access is assigned through application roles and database policies.</p>
        </article>
        <article className="panel">
          <h3>Status</h3>
          <p className="dashboard-value">{user.active ? "Active" : "Inactive"}</p>
          <p className="muted">Only active accounts can generate, preview, and execute queries.</p>
        </article>
      </div>

      <div className="grid">
        <article className="panel">
          <h3>Available Data Sources</h3>
          {connections.length === 0 ? (
            <p className="muted">No active data sources are currently available for your role.</p>
          ) : (
            <ul className="clean-list">
              {connections.map((connection) => (
                <li key={connection.id}>
                  <strong>{engineLabel(connection)}</strong>
                  <span>{connection.dialect}</span>
                </li>
              ))}
            </ul>
          )}
        </article>
        <article className="panel">
          <h3>Recent Query Activity</h3>
          {history.length === 0 ? (
            <p className="muted">Your generated and executed queries will appear here.</p>
          ) : (
            <ul className="clean-list">
              {history.map((item) => (
                <li key={item.id}>
                  <strong>{item.queryType}</strong>
                  <span>{item.executionStatus}: {item.userPrompt}</span>
                </li>
              ))}
            </ul>
          )}
        </article>
      </div>
    </section>
  );
}
