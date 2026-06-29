"""Preview and safe execution helpers for target relational databases."""

from __future__ import annotations

from typing import Any

import re
import sqlglot
from sqlalchemy import inspect
from sqlalchemy import text
from sqlalchemy.engine import Engine
from sqlglot import exp

from .row_level_security_service import RowLevelSecurityService
from .schemas import ExecuteResponse, InternalRequest, PreviewResponse
from .sql_security import (
    build_write_preview_sql,
    classify_query,
    classify_sql_command,
    validate_sql,
)


def preview_sql(engine: Engine, request: InternalRequest, dialect: str) -> PreviewResponse:
    generated_sql = request.generatedSql or ""
    validation = validate_sql(generated_sql, request.verifiedUser, request.accessPolicies, dialect)
    query_type = validation.queryType
    command_type = classify_sql_command(generated_sql)

    if query_type == "TCL":
        return PreviewResponse(
            generatedSql=generated_sql,
            finalEnforcedSql="",
            previewSql="",
            queryType="TCL",
            impactMessage="Transaction-control commands are explained but cannot be executed.",
            riskLevel="medium",
            executionAllowed=False,
            requiresConfirmation=False,
            warnings=validation.warnings,
            securityErrors=validation.securityErrors,
        )

    if not validation.isValid:
        return PreviewResponse(
            generatedSql=generated_sql,
            finalEnforcedSql="",
            previewSql="",
            queryType=query_type,
            impactMessage="SQL failed validation or authorization.",
            riskLevel="high",
            executionAllowed=False,
            requiresConfirmation=validation.requiresConfirmation,
            warnings=validation.warnings,
            securityErrors=validation.securityErrors,
        )

    rls_result = RowLevelSecurityService(request.verifiedUser, request.accessPolicies, dialect).enforce(validation.normalizedSql)
    if not rls_result.isEnforced:
        return PreviewResponse(
            generatedSql=generated_sql,
            finalEnforcedSql="",
            securityFilterExplanation=rls_result.securityFilterExplanation,
            previewSql="",
            queryType=query_type,
            impactMessage="Row-level authorization could not be safely enforced.",
            riskLevel="high",
            executionAllowed=False,
            requiresConfirmation=validation.requiresConfirmation,
            warnings=validation.warnings,
            securityErrors=rls_result.securityErrors,
        )
    final_sql = rls_result.finalEnforcedSql
    params = rls_result.parameters

    if command_type == "SELECT":
        preview_query = f"SELECT * FROM ({final_sql}) AS preview_source LIMIT 20"
        count_query = f"SELECT COUNT(*) AS estimated_rows FROM ({final_sql}) AS preview_source"
        with engine.connect() as connection:
            estimated_rows = int(connection.execute(text(count_query), params).scalar_one())
            rows = [dict(row) for row in connection.execute(text(preview_query), params).mappings().all()]
        return PreviewResponse(
            generatedSql=generated_sql,
            finalEnforcedSql=final_sql,
            securityFilterExplanation=rls_result.securityFilterExplanation,
            previewSql=preview_query,
            queryType=query_type,
            estimatedRows=estimated_rows,
            previewRows=rows,
            impactMessage=f"SELECT preview is limited to 20 rows. Estimated rows: {estimated_rows}.",
            riskLevel="low",
            executionAllowed=True,
            requiresConfirmation=False,
            warnings=validation.warnings,
        )

    if command_type in {"UPDATE", "DELETE"}:
        preview_query = build_write_preview_sql(final_sql, request.verifiedUser, request.accessPolicies, dialect)
        count_query = f"SELECT COUNT(*) AS estimated_rows FROM ({preview_query}) AS preview_source"
        limited_preview = f"SELECT * FROM ({preview_query}) AS preview_source LIMIT 20"
        with engine.connect() as connection:
            estimated_rows = int(connection.execute(text(count_query), params).scalar_one())
            rows = [dict(row) for row in connection.execute(text(limited_preview), params).mappings().all()]
        return PreviewResponse(
            generatedSql=generated_sql,
            finalEnforcedSql=final_sql,
            securityFilterExplanation=rls_result.securityFilterExplanation,
            previewSql=preview_query,
            queryType=query_type,
            estimatedRows=estimated_rows,
            previewRows=rows,
            impactMessage=f"{command_type} would affect approximately {estimated_rows} rows after enforcement.",
            riskLevel="high",
            executionAllowed=True,
            requiresConfirmation=True,
            warnings=validation.warnings + [f"{command_type} was not executed. This is only a preview."],
        )

    if command_type == "INSERT":
        missing_required_columns = _missing_required_insert_columns(engine, final_sql)
        if missing_required_columns:
            return PreviewResponse(
                generatedSql=generated_sql,
                finalEnforcedSql=final_sql,
                securityFilterExplanation=rls_result.securityFilterExplanation,
                previewSql="",
                queryType=query_type,
                estimatedRows=0,
                previewRows=[],
                impactMessage="INSERT is blocked because required table columns are missing.",
                riskLevel="high",
                executionAllowed=False,
                requiresConfirmation=True,
                warnings=validation.warnings,
                securityErrors=[
                    "INSERT must include required column(s): " + ", ".join(missing_required_columns)
                ],
            )
        insert_row_count = _estimate_insert_row_count(final_sql)
        return PreviewResponse(
            generatedSql=generated_sql,
            finalEnforcedSql=final_sql,
            securityFilterExplanation=rls_result.securityFilterExplanation,
            previewSql="",
            queryType=query_type,
            estimatedRows=insert_row_count,
            previewRows=[],
            impactMessage=(
                f"INSERT passed validation. It may add {insert_row_count} "
                f"{'row' if insert_row_count == 1 else 'rows'} and requires explicit confirmation before execution."
            ),
            riskLevel="high",
            executionAllowed=True,
            requiresConfirmation=True,
            warnings=validation.warnings + ["INSERT was not executed. This is only a validation preview."],
        )

    if query_type == "DDL":
        ddl_preview = _preview_ddl(engine, generated_sql, validation.normalizedSql, dialect)
        if ddl_preview:
            return PreviewResponse(
                generatedSql=generated_sql,
                finalEnforcedSql=final_sql,
                securityFilterExplanation=rls_result.securityFilterExplanation,
                previewSql="",
                queryType=query_type,
                estimatedRows=ddl_preview.get("estimatedRows", 0),
                previewRows=ddl_preview.get("previewRows", []),
                impactMessage=ddl_preview["impactMessage"],
                riskLevel=ddl_preview["riskLevel"],
                executionAllowed=validation.executionAllowed and not ddl_preview.get("blocked", False),
                requiresConfirmation=True,
                warnings=validation.warnings + ddl_preview.get("warnings", []),
                securityErrors=ddl_preview.get("securityErrors", []),
                requiredTypedConfirmation=ddl_preview.get("requiredTypedConfirmation"),
                ddlDetails=ddl_preview.get("ddlDetails", {}),
            )
        return PreviewResponse(
            generatedSql=generated_sql,
            finalEnforcedSql=final_sql,
            securityFilterExplanation=rls_result.securityFilterExplanation,
            previewSql="",
            queryType=query_type,
            estimatedRows=0,
            previewRows=[],
            impactMessage="DDL passed validation. It was not executed during preview and requires explicit confirmation.",
            riskLevel="high" if validation.requiresConfirmation else "medium",
            executionAllowed=validation.executionAllowed,
            requiresConfirmation=validation.requiresConfirmation,
            warnings=validation.warnings + ["DDL was not executed. This is only a validation preview."],
        )

    return PreviewResponse(
        generatedSql=generated_sql,
        finalEnforcedSql=final_sql,
        securityFilterExplanation=rls_result.securityFilterExplanation,
        previewSql="",
        queryType=query_type,
        impactMessage=f"{query_type} preview is not available.",
        riskLevel="medium",
        executionAllowed=validation.executionAllowed,
        requiresConfirmation=validation.requiresConfirmation,
        warnings=validation.warnings,
    )


def execute_sql(engine: Engine, request: InternalRequest, dialect: str) -> ExecuteResponse:
    generated_sql = request.generatedSql or ""
    query_type = classify_query(generated_sql)
    command_type = classify_sql_command(generated_sql)

    if query_type == "TCL":
        return _blocked(generated_sql, "TCL", "Transaction-control commands are explained but cannot be executed.")
    if query_type == "DCL":
        return _blocked(
            generated_sql,
            query_type,
            "GRANT and REVOKE are not executable because permission management is restricted.",
        )

    validation = validate_sql(generated_sql, request.verifiedUser, request.accessPolicies, dialect)
    if not validation.isValid:
        return _blocked(
            generated_sql,
            query_type,
            validation.securityErrors[0] if validation.securityErrors else "SQL failed validation or authorization.",
        )
    if not validation.executionAllowed:
        return _blocked(
            generated_sql,
            query_type,
            validation.securityErrors[0] if validation.securityErrors else f"{query_type} execution is not allowed.",
        )

    rls_result = RowLevelSecurityService(request.verifiedUser, request.accessPolicies, dialect).enforce(validation.normalizedSql)
    if not rls_result.isEnforced:
        return _blocked(
            generated_sql,
            query_type,
            "Row-level authorization could not be safely enforced.",
            "",
            rls_result.securityFilterExplanation,
        )
    final_sql = rls_result.finalEnforcedSql
    params = rls_result.parameters

    if command_type == "SELECT":
        execution_sql = f"SELECT * FROM ({final_sql}) AS execution_source LIMIT 100"
        with engine.connect() as connection:
            rows = [dict(row) for row in connection.execute(text(execution_sql), params).mappings().all()]
        return ExecuteResponse(
            success=True,
            message="SELECT executed successfully.",
            generatedSql=generated_sql,
            finalEnforcedSql=execution_sql,
            securityFilterExplanation=rls_result.securityFilterExplanation,
            queryType=query_type,
            rowsAffected=len(rows),
            resultRows=rows,
            executionAllowed=True,
        )

    if command_type == "DDL":
        ddl_preview = _preview_ddl(engine, generated_sql, final_sql, dialect)
        if ddl_preview and ddl_preview.get("blocked", False):
            return _blocked(
                generated_sql,
                query_type,
                ddl_preview["impactMessage"],
                final_sql,
                rls_result.securityFilterExplanation,
            )

    if command_type == "INSERT":
        missing_required_columns = _missing_required_insert_columns(engine, final_sql)
        if missing_required_columns:
            return _blocked(
                generated_sql,
                query_type,
                "INSERT must include required column(s): " + ", ".join(missing_required_columns),
                final_sql,
                rls_result.securityFilterExplanation,
            )

    if validation.requiresConfirmation and not request.confirmed:
        return _blocked(
            generated_sql,
            query_type,
            f"{query_type} requires explicit confirmation.",
            final_sql,
            rls_result.securityFilterExplanation,
        )
    if command_type == "DDL" and _ddl_command(final_sql) == "DROP_TABLE":
        table_name = _simple_table_name_from_drop(final_sql)
        if not table_name or request.typedConfirmation != table_name:
            return _blocked(
                generated_sql,
                query_type,
                f"DROP TABLE requires typing the exact table name: {table_name}.",
                final_sql,
                rls_result.securityFilterExplanation,
            )

    with engine.begin() as connection:
        result = connection.execute(text(final_sql), params)
        rows_affected = int(result.rowcount or 0)
        result_rows = _rows_after_insert(connection, final_sql, dialect) if command_type == "INSERT" else []

    return ExecuteResponse(
        success=True,
        message=f"{command_type if command_type != 'DDL' else query_type} executed successfully.",
        generatedSql=generated_sql,
        finalEnforcedSql=final_sql,
        securityFilterExplanation=rls_result.securityFilterExplanation,
        queryType=query_type,
        rowsAffected=rows_affected,
        resultRows=result_rows,
        executionAllowed=True,
    )


def _preview_ddl(engine: Engine, generated_sql: str, final_sql: str, dialect: str) -> dict[str, Any] | None:
    ddl_command = _ddl_command(final_sql)
    if ddl_command == "CREATE_TABLE":
        table_name = _simple_table_name_from_create(final_sql)
        if not table_name:
            return {
                "blocked": True,
                "impactMessage": "CREATE TABLE preview failed because the table name could not be safely identified.",
                "riskLevel": "high",
                "securityErrors": ["CREATE TABLE requires a simple table name."],
            }
        inspector = inspect(engine)
        exists = _table_exists(inspector, table_name)
        return {
            "blocked": exists,
            "impactMessage": (
                f"CREATE TABLE would create '{table_name}' after confirmation."
                if not exists
                else f"CREATE TABLE is blocked because '{table_name}' already exists."
            ),
            "riskLevel": "high",
            "warnings": ["CREATE TABLE changes database structure and requires explicit confirmation."],
            "securityErrors": [f"Table '{table_name}' already exists."] if exists else [],
            "ddlDetails": {"operation": "CREATE_TABLE", "tableName": table_name, "tableExists": exists},
        }
    if ddl_command == "DROP_TABLE":
        table_name = _simple_table_name_from_drop(final_sql)
        if not table_name:
            return {
                "blocked": True,
                "impactMessage": "DROP TABLE preview failed because only a simple unquoted table name is allowed.",
                "riskLevel": "critical",
                "securityErrors": ["DROP TABLE allows only one simple unquoted table name."],
            }
        inspector = inspect(engine)
        exists = _table_exists(inspector, table_name)
        if not exists:
            return {
                "blocked": True,
                "impactMessage": f"DROP TABLE is blocked because '{table_name}' does not exist.",
                "riskLevel": "critical",
                "securityErrors": [f"Table '{table_name}' does not exist."],
                "requiredTypedConfirmation": table_name,
                "ddlDetails": {"operation": "DROP_TABLE", "tableName": table_name, "tableExists": False},
            }
        columns = [{"name": column["name"], "type": str(column["type"]).upper()} for column in inspector.get_columns(table_name)]
        row_count = _safe_count_table_rows(engine, table_name)
        return {
            "blocked": False,
            "impactMessage": f"This permanently deletes the {table_name} table and all of its data.",
            "riskLevel": "critical",
            "warnings": [
                f"This permanently deletes the {table_name} table and all of its data.",
                "Deleted rows and table structure cannot be restored through this application.",
            ],
            "estimatedRows": row_count,
            "previewRows": columns,
            "requiredTypedConfirmation": table_name,
            "ddlDetails": {
                "operation": "DROP_TABLE",
                "tableName": table_name,
                "tableExists": True,
                "columns": columns,
                "approximateRowCount": row_count,
            },
        }
    return None


def _ddl_command(sql: str) -> str:
    normalized = re.sub(r"\s+", " ", sql.strip().rstrip(";")).upper()
    if normalized.startswith("CREATE TABLE"):
        return "CREATE_TABLE"
    if normalized.startswith("DROP TABLE"):
        return "DROP_TABLE"
    if normalized.startswith("ALTER TABLE"):
        return "ALTER_TABLE"
    if normalized.startswith("CREATE INDEX"):
        return "CREATE_INDEX"
    if normalized.startswith("CREATE VIEW"):
        return "CREATE_VIEW"
    return "DDL"


def _simple_table_name_from_create(sql: str) -> str | None:
    match = re.match(r"\s*CREATE\s+TABLE\s+([A-Za-z_][A-Za-z0-9_]*)\b", sql, flags=re.IGNORECASE)
    return match.group(1) if match else None


def _simple_table_name_from_drop(sql: str) -> str | None:
    match = re.fullmatch(r"\s*DROP\s+TABLE\s+([A-Za-z_][A-Za-z0-9_]*)\s*;?\s*", sql, flags=re.IGNORECASE)
    return match.group(1) if match else None


def _table_exists(inspector: Any, table_name: str) -> bool:
    return table_name.lower() in {table.lower() for table in inspector.get_table_names()}


def _missing_required_insert_columns(engine: Engine, sql: str) -> list[str]:
    table_name, insert_columns = _insert_target_and_columns(sql)
    if not table_name or not insert_columns:
        return []
    schema_name = getattr(engine, "_workspace_schema", None)
    inspector = inspect(engine)
    if not _table_exists_in_schema(inspector, table_name, schema_name):
        return []
    required = []
    for column in inspector.get_columns(table_name, schema=schema_name):
        if column.get("default") is not None:
            continue
        if column.get("primary_key", False) or not column.get("nullable", True):
            required.append(column["name"].lower())
    return sorted(set(required) - {column.lower() for column in insert_columns})


def _insert_target_and_columns(sql: str) -> tuple[str, list[str]]:
    match = re.search(
        r"\bINSERT\s+INTO\s+([A-Za-z_][A-Za-z0-9_]*)\s*\(([^)]*)\)",
        sql,
        flags=re.IGNORECASE | re.DOTALL,
    )
    if not match:
        return "", []
    columns = [
        value.strip().strip('"`[]')
        for value in match.group(2).split(",")
        if value.strip()
    ]
    return match.group(1), columns


def _estimate_insert_row_count(sql: str) -> int:
    try:
        expression = sqlglot.parse_one(sql)
        values = expression.find(exp.Values)
        if values is not None and values.expressions:
            return len(values.expressions)
    except Exception:
        pass

    values_match = re.search(r"\bVALUES\b(.+)$", sql.strip().rstrip(";"), flags=re.IGNORECASE | re.DOTALL)
    if not values_match:
        return 1

    values_sql = values_match.group(1)
    depth = 0
    in_string = False
    quote = ""
    row_count = 0
    for index, char in enumerate(values_sql):
        previous = values_sql[index - 1] if index > 0 else ""
        if in_string:
            if char == quote and previous != "\\":
                in_string = False
            continue
        if char in {"'", '"'}:
            in_string = True
            quote = char
            continue
        if char == "(":
            if depth == 0:
                row_count += 1
            depth += 1
        elif char == ")" and depth > 0:
            depth -= 1
    return max(1, row_count)


def _rows_after_insert(connection: Any, sql: str, dialect: str) -> list[dict[str, Any]]:
    target = _insert_target_details(sql, dialect)
    if not target:
        return []
    table_name, columns, rows = target
    if len(rows) > 20:
        rows = rows[:20]
    where_parts = []
    params: dict[str, Any] = {}
    for row_index, row_values in enumerate(rows):
        column_parts = []
        for column_index, (column, value) in enumerate(zip(columns, row_values)):
            param_name = f"v_{row_index}_{column_index}"
            column_parts.append(f"{column} = :{param_name}")
            params[param_name] = value
        where_parts.append("(" + " AND ".join(column_parts) + ")")
    if not where_parts:
        return []
    query = f"SELECT * FROM {table_name} WHERE {' OR '.join(where_parts)} LIMIT 20"
    return [dict(row) for row in connection.execute(text(query), params).mappings().all()]


def _insert_target_details(sql: str, dialect: str) -> tuple[str, list[str], list[list[Any]]] | None:
    try:
        expression = sqlglot.parse_one(sql, dialect=dialect)
    except sqlglot.errors.ParseError:
        return None
    if not isinstance(expression, exp.Insert) or not isinstance(expression.this, exp.Schema):
        return None
    table_expression = expression.this.this
    if not isinstance(table_expression, exp.Table) or not _safe_identifier(table_expression.name):
        return None
    columns = []
    for identifier in expression.this.expressions:
        if not isinstance(identifier, exp.Identifier) or not _safe_identifier(identifier.name):
            return None
        columns.append(identifier.name)
    values = expression.find(exp.Values)
    if values is None:
        return None
    rows: list[list[Any]] = []
    for tuple_expression in values.expressions:
        row_values = []
        for value_expression in tuple_expression.expressions:
            literal_value = _literal_value(value_expression)
            if literal_value is _UNSUPPORTED_LITERAL:
                return None
            row_values.append(literal_value)
        if len(row_values) != len(columns):
            return None
        rows.append(row_values)
    return table_expression.name, columns, rows


_UNSUPPORTED_LITERAL = object()


def _literal_value(value_expression: exp.Expression) -> Any:
    if isinstance(value_expression, exp.Null):
        return None
    if isinstance(value_expression, exp.Boolean):
        return bool(value_expression.this)
    if isinstance(value_expression, exp.Literal):
        if value_expression.is_string:
            return value_expression.this
        raw_value = str(value_expression.this)
        if re.fullmatch(r"-?\d+", raw_value):
            return int(raw_value)
        if re.fullmatch(r"-?\d+\.\d+", raw_value):
            return float(raw_value)
        return raw_value
    return _UNSUPPORTED_LITERAL


def _safe_identifier(value: str) -> bool:
    return bool(re.fullmatch(r"[A-Za-z_][A-Za-z0-9_]*", value or ""))


def _table_exists_in_schema(inspector: Any, table_name: str, schema_name: str | None = None) -> bool:
    return table_name.lower() in {table.lower() for table in inspector.get_table_names(schema=schema_name)}


def _safe_count_table_rows(engine: Engine, table_name: str) -> int:
    if not re.fullmatch(r"[A-Za-z_][A-Za-z0-9_]*", table_name):
        return 0
    with engine.connect() as connection:
        return int(connection.execute(text(f"SELECT COUNT(*) AS total_rows FROM {table_name}")).scalar_one())


def _blocked(
    generated_sql: str,
    query_type: str,
    message: str,
    final_sql: str = "",
    security_filter_explanation: str = "",
) -> ExecuteResponse:
    return ExecuteResponse(
        success=False,
        message=message,
        generatedSql=generated_sql,
        finalEnforcedSql=final_sql,
        securityFilterExplanation=security_filter_explanation,
        queryType=query_type,
        rowsAffected=0,
        resultRows=[],
        executionAllowed=False,
    )
