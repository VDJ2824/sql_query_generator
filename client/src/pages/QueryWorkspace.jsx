import {useEffect, useMemo, useState} from "react";
import {useAuth} from "../auth/AuthContext";
import {ApiClient} from "../services/ApiClient";

function normalizedType(value = "") {
  return String(value || "").toUpperCase();
}

function isWriteQuery(queryType) {
  return ["DML", "UPDATE", "INSERT", "DELETE"].includes(normalizedType(queryType));
}

function isSchemaQuery(queryType) {
  return normalizedType(queryType) === "DDL";
}

function isBlockedDisplayType(queryType) {
  return ["TCL", "DCL"].includes(normalizedType(queryType));
}

function executionAllowed(payload) {
  if (!payload) return false;
  return Boolean(payload.executionAllowed ?? payload.execution_allowed ?? false);
}

function databaseLabel(connection) {
  if (!connection) return "";
  if (connection.databaseType === "postgresql") return "PostgreSQL";
  if (connection.databaseType === "mysql") return "MySQL";
  return connection.databaseType;
}

function requiresConfirmation(payload) {
  if (!payload) return false;
  return Boolean(payload.requiresConfirmation ?? payload.requires_confirmation ?? false);
}

function SqlBlock({title, sql}) {
  if (!sql) return null;
  return (
    <div>
      <h4>{title}</h4>
      <pre className="sql-block">{sql}</pre>
    </div>
  );
}

function PreviewTable({rows = []}) {
  if (!rows.length) {
    return <p className="empty-state">No preview rows returned.</p>;
  }
  const columns = Object.keys(rows[0]);
  return (
    <div className="table-wrap">
      <table>
        <thead>
          <tr>{columns.map((column) => <th key={column}>{column}</th>)}</tr>
        </thead>
        <tbody>
          {rows.map((row, index) => (
            <tr key={index}>
              {columns.map((column) => <td key={column}>{String(row[column] ?? "")}</td>)}
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}

export function QueryWorkspace() {
  const {user} = useAuth();
  const [connections, setConnections] = useState([]);
  const [selectedConnectionId, setSelectedConnectionId] = useState("");
  const [prompt, setPrompt] = useState("Create a table named Student with columns id, name, roll_no, and email.");
  const [options, setOptions] = useState([]);
  const [selectedOptionId, setSelectedOptionId] = useState("");
  const [preview, setPreview] = useState(null);
  const [execution, setExecution] = useState(null);
  const [message, setMessage] = useState("");
  const [loading, setLoading] = useState("");
  const [showConfirm, setShowConfirm] = useState(false);
  const [typedConfirmation, setTypedConfirmation] = useState("");

  const selectedConnection = useMemo(
    () => connections.find((connection) => connection.id === selectedConnectionId),
    [connections, selectedConnectionId],
  );

  const selectedOption = useMemo(
    () => options.find((option) => String(option.option_id ?? option.optionId) === String(selectedOptionId)),
    [options, selectedOptionId],
  );

  const currentQueryType = normalizedType(preview?.queryType || preview?.query_type || selectedOption?.query_type || selectedOption?.queryType);
  const requiredTypedConfirmation = preview?.requiredTypedConfirmation || preview?.required_typed_confirmation || "";
  const confirmationToken = preview?.confirmationToken || preview?.confirmation_token || "";
  const canShowExecute = preview && executionAllowed(preview) && !isBlockedDisplayType(currentQueryType);
  const confirmationTitle = isSchemaQuery(currentQueryType)
    ? "This operation changes database structure."
    : "This operation may modify data.";

  useEffect(() => {
    setLoading("connections");
    ApiClient.listDatabaseConnections()
      .then((response) => {
        setConnections(response.databaseConnections || []);
        if (response.databaseConnections?.length) {
          setSelectedConnectionId(response.databaseConnections[0].id);
        }
      })
      .catch((error) => setMessage(error.message || "Could not load allowed database connections."))
      .finally(() => setLoading(""));
  }, []);

  async function generateOptions(event) {
    event.preventDefault();
    setMessage("");
    setPreview(null);
    setExecution(null);
    setTypedConfirmation("");
    setOptions([]);
    setSelectedOptionId("");

    if (!selectedConnectionId) {
      setMessage("Choose a data source before generating SQL.");
      return;
    }
    if (!prompt.trim()) {
      setMessage("Enter a request in plain English.");
      return;
    }

    setLoading("generate");
    try {
      const response = await ApiClient.generateQueryOptions({
        databaseConnectionId: selectedConnectionId,
        prompt,
      });
      setOptions(response.query_options || response.queryOptions || []);
      if (!(response.query_options || response.queryOptions || []).length) {
        setMessage("No safe query options were returned for this request.");
      }
    } catch (error) {
      setMessage(error.message || "Unable to generate SQL right now.");
    } finally {
      setLoading("");
    }
  }

  async function selectAndPreview() {
    setMessage("");
    setPreview(null);
    setExecution(null);
    setTypedConfirmation("");

    if (!selectedConnectionId || !selectedOption) {
      setMessage("Choose one data source and one generated option before previewing.");
      return;
    }

    setLoading("preview");
    try {
      await ApiClient.selectQuery(selectedConnectionId, {
        optionId: selectedOption.option_id ?? selectedOption.optionId,
      });
      const response = await ApiClient.previewSelectedQuery({
        databaseConnectionId: selectedConnectionId,
        selectedOptionId: selectedOption.option_id ?? selectedOption.optionId,
      });
      setPreview(response);
    } catch (error) {
      setMessage(error.message || "Preview failed.");
    } finally {
      setLoading("");
    }
  }

  async function executeSelected(confirmed = false) {
    setShowConfirm(false);
    setMessage("");

    if (!preview || !canShowExecute) {
      setMessage("Execution is not allowed for the current query.");
      return;
    }

    setLoading("execute");
    try {
      const response = await ApiClient.executeSelectedQuery({
        databaseConnectionId: selectedConnectionId,
        selectedOptionId: selectedOption.option_id ?? selectedOption.optionId,
        confirmed,
        confirmationToken,
        typedConfirmation,
      });
      setExecution(response);
    } catch (error) {
      setMessage(error.message || "Execution failed.");
    } finally {
      setLoading("");
    }
  }

  function handleExecuteClick() {
    if (requiresConfirmation(preview) || isWriteQuery(currentQueryType)) {
      setShowConfirm(true);
      return;
    }
    executeSelected(false);
  }

  return (
    <section className="page-stack">
      <div className="hero-card">
        <p className="eyebrow">Query Studio</p>
        <h2>Generate and run SQL safely</h2>
        <p>
          Signed in as <strong>{user.username}</strong> with <strong>{user.role}</strong> access.
          Choose a data source, describe the query you need, then review backend-validated SQL before execution.
        </p>
      </div>

      {message && <p className="notice error-notice">{message}</p>}

      <section className="panel">
        <div className="section-heading">
          <div>
            <p className="eyebrow">Step 1</p>
            <h3>Select a data source</h3>
          </div>
          {loading === "connections" && <span className="pill">Loading...</span>}
        </div>
        <label>
          Available engines
          <select value={selectedConnectionId} onChange={(event) => setSelectedConnectionId(event.target.value)}>
            <option value="">Select a database</option>
            {connections.map((connection) => (
              <option value={connection.id} key={connection.id}>
                {databaseLabel(connection)}
              </option>
            ))}
          </select>
        </label>
        {selectedConnection ? (
          <div className="selected-db-card">
            <strong>{databaseLabel(selectedConnection)}</strong>
            <span>Dialect: {selectedConnection.dialect}</span>
          </div>
        ) : (
          <p className="empty-state">Choose an available data source to begin.</p>
        )}
      </section>

      <form className="panel form-panel" onSubmit={generateOptions}>
        <div className="section-heading">
          <div>
            <p className="eyebrow">Step 2</p>
            <h3>Describe your SQL request</h3>
          </div>
          <span className="pill">Backend validated</span>
        </div>
        <label>
          Natural-language prompt
          <textarea value={prompt} onChange={(event) => setPrompt(event.target.value)} />
        </label>
        <button type="submit" disabled={loading === "generate"}>
          {loading === "generate" ? "Generating..." : "Generate SQL Options"}
        </button>
      </form>

      <section className="panel">
        <div className="section-heading">
          <div>
            <p className="eyebrow">Step 3</p>
            <h3>Review generated options</h3>
          </div>
          <button type="button" onClick={selectAndPreview} disabled={loading === "preview" || !selectedOption}>
            {loading === "preview" ? "Preparing preview..." : "Preview Selected Option"}
          </button>
        </div>

        {!options.length ? (
          <p className="empty-state">Generated SQL options will appear here after the backend validates the request.</p>
        ) : (
          <div className="option-grid">
            {options.map((option) => {
              const optionId = option.option_id ?? option.optionId;
              const queryType = normalizedType(option.query_type || option.queryType);
              const warnings = option.warnings || [];
              return (
                <article className="option-card" key={optionId}>
                  <label className="radio-row">
                    <input
                      type="radio"
                      name="query-option"
                      checked={String(selectedOptionId) === String(optionId)}
                      onChange={() => setSelectedOptionId(String(optionId))}
                    />
                    <span>
                      <strong>{option.title}</strong>
                      <small>{option.explanation}</small>
                    </span>
                  </label>
                  {isWriteQuery(queryType) && (
                    <p className="warning">Warning: DML may modify data and must follow backend preview and confirmation rules.</p>
                  )}
                  {queryType === "DDL" && (
                    <p className="warning">
                      Safe table-level DDL, such as CREATE TABLE, can run only after backend preview and explicit confirmation.
                      Database-level administration, such as CREATE DATABASE, stays blocked.
                    </p>
                  )}
                  {queryType === "TCL" && <p className="warning">Transaction-control commands are explained but cannot be executed.</p>}
                  {queryType === "DCL" && (
                    <p className="warning">GRANT and REVOKE are not executable because permission management is restricted.</p>
                  )}
                  <SqlBlock title="Generated SQL" sql={option.sql || option.generatedSql} />
                  <div className="meta-row">
                    <span className="pill">Type: {queryType || "-"}</span>
                    <span className="pill">Risk: {option.risk_level || option.riskLevel || "-"}</span>
                    <span className="pill">Execution allowed: {String(option.execution_allowed ?? option.executionAllowed ?? false)}</span>
                  </div>
                  {!!warnings.length && <ul className="warning-list">{warnings.map((warning) => <li key={warning}>{warning}</li>)}</ul>}
                </article>
              );
            })}
          </div>
        )}
      </section>

      <section className="panel">
        <div className="section-heading">
          <div>
            <p className="eyebrow">Step 4</p>
            <h3>Preview impact</h3>
          </div>
          {preview && <span className="pill">Query type: {currentQueryType || "-"}</span>}
        </div>

        {!preview ? (
          <p className="empty-state">Preview shows generated SQL, preview SQL, and security-enforced SQL separately before execution.</p>
        ) : (
          <div className="preview-stack">
            <p><strong>Estimated rows:</strong> {preview.estimatedRows ?? preview.estimated_rows ?? 0}</p>
            <p><strong>Impact:</strong> {preview.impactMessage || preview.impact_message || "-"}</p>
            {currentQueryType === "TCL" && <p className="warning">Transaction-control commands are explained but cannot be executed.</p>}
            {currentQueryType === "DCL" && (
              <p className="warning">GRANT and REVOKE are not executable because permission management is restricted.</p>
            )}
            {isWriteQuery(currentQueryType) && (
              <p className="warning">Warning: DML can modify data. Confirm only after reviewing backend-enforced SQL.</p>
            )}
            {currentQueryType === "DDL" && (
              <p className="warning">
                Safe table-level DDL can be executed after this backend preview and your confirmation.
                Database-level administration, such as CREATE DATABASE, is blocked for security.
              </p>
            )}
            {preview.ddlDetails?.operation === "CREATE_TABLE" && executionAllowed(preview) && (
              <div className="selected-db-card">
                <strong>CREATE TABLE is ready for confirmation.</strong>
                <span>Preview did not execute the statement. Use Execute Selected Query to create the table.</span>
              </div>
            )}
            {preview.ddlDetails?.operation === "DROP_TABLE" && (
              <div className="danger-panel">
                <h4>Dangerous DROP TABLE Preview</h4>
                <p><strong>Table:</strong> {preview.ddlDetails.tableName}</p>
                <p><strong>Approximate rows:</strong> {preview.ddlDetails.approximateRowCount ?? preview.estimatedRows ?? 0}</p>
                <p className="warning">This permanently deletes the {preview.ddlDetails.tableName} table and all of its data.</p>
              </div>
            )}
            <SqlBlock title="Generated SQL" sql={preview.generatedSql || preview.generated_sql} />
            <SqlBlock title="Preview Query" sql={preview.previewSql || preview.preview_sql} />
            <SqlBlock title="Security-Enforced SQL" sql={preview.finalEnforcedSql || preview.final_enforced_sql} />
            <PreviewTable rows={preview.previewRows || preview.preview_rows || []} />
            {canShowExecute ? (
              <button type="button" onClick={handleExecuteClick} disabled={loading === "execute"}>
                {loading === "execute" ? "Executing..." : "Execute Selected Query"}
              </button>
            ) : (
              <p className="empty-state">Execute button hidden because backend response does not allow execution.</p>
            )}
          </div>
        )}
      </section>

      <section className="panel">
        <div className="section-heading">
          <div>
            <p className="eyebrow">Step 5</p>
            <h3>Execution result</h3>
          </div>
        </div>
        {!execution ? (
          <p className="empty-state">Execution results appear here after backend approval and confirmation.</p>
        ) : (
          <div>
            <p><strong>Status:</strong> {execution.success ? "Success" : "Blocked"}</p>
            <p>{execution.message}</p>
            <SqlBlock title="Generated SQL" sql={execution.generatedSql || execution.generated_sql} />
            <SqlBlock title="Security-Enforced SQL" sql={execution.finalEnforcedSql || execution.final_enforced_sql} />
            <PreviewTable rows={execution.resultRows || execution.result_rows || []} />
          </div>
        )}
      </section>

      {showConfirm && (
        <div className="modal-backdrop" role="dialog" aria-modal="true">
          <div className="modal-card">
            <p className="eyebrow">Confirmation required</p>
            <h3>{confirmationTitle}</h3>
            <p>Do you want to continue with the backend-approved {currentQueryType} execution?</p>
            {requiredTypedConfirmation && (
              <label>
                Type {requiredTypedConfirmation} to permanently drop the table
                <input
                  value={typedConfirmation}
                  onChange={(event) => setTypedConfirmation(event.target.value)}
                  placeholder={requiredTypedConfirmation}
                />
              </label>
            )}
            <div className="modal-actions">
              <button
                type="button"
                className="danger-button"
                onClick={() => executeSelected(true)}
                disabled={requiredTypedConfirmation && typedConfirmation !== requiredTypedConfirmation}
              >
                Continue
              </button>
              <button type="button" className="ghost-button" onClick={() => setShowConfirm(false)}>Cancel</button>
            </div>
          </div>
        </div>
      )}
    </section>
  );
}
