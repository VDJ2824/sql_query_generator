import {useEffect, useState} from "react";
import {ApiClient} from "../services/ApiClient";

export function History() {
  const [history, setHistory] = useState([]);
  const [message, setMessage] = useState("");

  useEffect(() => {
    ApiClient.history()
      .then((response) => setHistory(response.history))
      .catch((error) => setMessage(error.message || "Could not load history."));
  }, []);

  return (
    <section className="page-stack">
      <div className="hero-card">
        <p className="eyebrow">Personal Activity</p>
        <h2>Query History</h2>
        <p>Track your generated, previewed, and executed SQL requests. Your history is visible only to your account.</p>
      </div>
      {message && <p className="notice">{message}</p>}
      <div className="card-list">
        {history.map((item) => (
          <article className="panel" key={item.id}>
            <h3>{item.queryType} - {item.executionStatus}</h3>
            <p>{item.userPrompt}</p>
            <small>Rows affected: {item.rowsAffected ?? "-"} | {new Date(item.createdAt).toLocaleString()}</small>
          </article>
        ))}
        {!history.length && !message && <p className="empty-state">No query history yet. Generate a query to start building your activity log.</p>}
      </div>
    </section>
  );
}
