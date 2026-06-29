import {useEffect, useState} from "react";
import {ApiClient} from "../services/ApiClient";

export function AdminAuditLogs() {
  const [auditLogs, setAuditLogs] = useState([]);
  const [message, setMessage] = useState("");

  useEffect(() => {
    ApiClient.auditLogs()
      .then((response) => setAuditLogs(response.auditLogs))
      .catch((error) => setMessage(error.message || "Could not load audit logs."));
  }, []);

  return (
    <section className="page-stack">
      <div className="hero-card">
        <p className="eyebrow">Administrator View</p>
        <h2>Security Audit Log</h2>
        <p>Review authentication, generation, preview, execution, and blocked-query events without exposing passwords or secrets.</p>
      </div>
      {message && <p className="notice">{message}</p>}
      <div className="card-list">
        {auditLogs.map((log) => (
          <article className="panel" key={log.id}>
            <h3>{log.action} - {log.status}</h3>
            <p>{log.message}</p>
            <small>{new Date(log.createdAt).toLocaleString()}</small>
          </article>
        ))}
        {!auditLogs.length && !message && <p className="empty-state">No audit events have been recorded yet.</p>}
      </div>
    </section>
  );
}
