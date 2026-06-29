import {useEffect, useState} from "react";
import {useAuth} from "../auth/AuthContext";
import {ApiClient} from "../services/ApiClient";

function engineLabel(connection) {
  if (connection?.databaseType === "mysql") return "MySQL";
  if (connection?.databaseType === "postgresql") return "PostgreSQL";
  return connection?.databaseType || "SQL";
}

export function DatabaseConnections() {
  const {user} = useAuth();
  const [connections, setConnections] = useState([]);
  const [tablesByConnectionId, setTablesByConnectionId] = useState({});
  const [selectedConnectionId, setSelectedConnectionId] = useState("");
  const [form, setForm] = useState({
    connectionName: "",
    databaseType: "postgresql",
    dialect: "postgres",
    credentialEnvironmentVariableName: "",
    allowedRoles: "USER,ADMIN",
  });
  const [message, setMessage] = useState("");

  async function loadConnections() {
    const response = await ApiClient.listDatabaseConnections();
    const nextConnections = response.databaseConnections || [];
    setConnections(nextConnections);
    if (!selectedConnectionId && nextConnections.length) {
      setSelectedConnectionId(nextConnections[0].id);
    }
  }

  useEffect(() => {
    loadConnections().catch((error) => setMessage(error.response?.data?.message || "Could not load connections."));
  }, []);

  useEffect(() => {
    let active = true;
    async function loadTables() {
      const entries = await Promise.all(
        connections.map(async (connection) => {
          try {
            const response = await ApiClient.listDatabaseTables(connection.id);
            return [connection.id, {status: "loaded", tables: response.tables || []}];
          } catch (error) {
            return [connection.id, {status: "error", message: error.message || "Could not load tables."}];
          }
        }),
      );
      if (active) {
        setTablesByConnectionId(Object.fromEntries(entries));
      }
    }
    if (connections.length) {
      loadTables();
    } else {
      setTablesByConnectionId({});
    }
    return () => {
      active = false;
    };
  }, [connections]);

  async function createConnection(event) {
    event.preventDefault();
    setMessage("");
    try {
      await ApiClient.createDatabaseConnection({
        ...form,
        allowedRoles: form.allowedRoles.split(",").map((role) => role.trim()).filter(Boolean),
      });
      setForm({...form, connectionName: ""});
      await loadConnections();
      setMessage("Connection metadata created.");
    } catch (error) {
      setMessage(error.response?.data?.message || "Could not create connection.");
    }
  }

  return (
    <section className="page-stack">
      <div className="hero-card">
        <p className="eyebrow">Data Sources</p>
        <h2>Manage Database Access</h2>
        <p>Connect the application to approved SQL engines without exposing raw credentials in the browser.</p>
      </div>

      {user?.role === "ADMIN" ? (
        <form className="panel form-panel" onSubmit={createConnection}>
          <h3>Add a data source</h3>
          <p className="muted">Store only the environment variable name that points to the credential. Never paste raw database URLs here.</p>
          <label>
            Connection name
            <input value={form.connectionName} onChange={(event) => setForm({...form, connectionName: event.target.value})} />
          </label>
          <label>
            Database type
            <select
              value={form.databaseType}
              onChange={(event) => {
                const databaseType = event.target.value;
                const dialect = {postgresql: "postgres", mysql: "mysql"}[databaseType];
                setForm({...form, databaseType, dialect});
              }}
            >
              <option value="postgresql">PostgreSQL</option>
              <option value="mysql">MySQL</option>
            </select>
          </label>
          <label>
            SQL dialect
            <input value={form.dialect} onChange={(event) => setForm({...form, dialect: event.target.value})} />
          </label>
          <label>
            Credential environment variable name
            <input value={form.credentialEnvironmentVariableName} onChange={(event) => setForm({...form, credentialEnvironmentVariableName: event.target.value})} />
          </label>
          <label>
            Allowed roles
            <input value={form.allowedRoles} onChange={(event) => setForm({...form, allowedRoles: event.target.value})} />
          </label>
          <button type="submit">Add Data Source</button>
        </form>
      ) : (
        <div className="panel">
          <h3>Available data sources</h3>
          <p className="muted">Your role can view approved data sources. Only administrators can add or modify them.</p>
        </div>
      )}

      {message && <p className="notice">{message}</p>}

      <section className="panel">
        <h3>Choose a data source</h3>
        <p className="muted">Use this list to review available engines. The Query Studio asks you to choose the target engine before generation.</p>
        <div className="option-grid compact-options">
          {connections.map((connection) => (
            <button
              type="button"
              className={selectedConnectionId === connection.id ? "select-card active" : "select-card"}
              key={connection.id}
              onClick={() => setSelectedConnectionId(connection.id)}
            >
              <strong>{engineLabel(connection)}</strong>
              <span>{connection.dialect}</span>
            </button>
          ))}
        </div>
      </section>

      <div className="card-list">
        {connections.map((connection) => (
          <article className="panel" key={connection.id}>
            <h3>{engineLabel(connection)}</h3>
            <p><strong>Dialect:</strong> {connection.dialect}</p>
            <TableListState state={tablesByConnectionId[connection.id]} />
          </article>
        ))}
      </div>
    </section>
  );
}

function TableListState({state}) {
  if (!state) {
    return <p className="muted">Loading tables...</p>;
  }
  if (state.status === "error") {
    return <p className="muted">Tables unavailable: {state.message}</p>;
  }
  if (!state.tables.length) {
    return <p className="muted">No tables found in your current workspace.</p>;
  }
  return (
    <div>
      <p><strong>Tables:</strong></p>
      <div className="table-chip-row">
        {state.tables.map((tableName) => (
          <span className="table-chip" key={tableName}>{tableName}</span>
        ))}
      </div>
    </div>
  );
}
