"""SQL classification, validation, and row-level enforcement."""

from __future__ import annotations

import re
from typing import Any

import sqlglot
from sqlglot import exp

from .policies import (
    all_workspace_tables_allowed,
    allowed_columns_for_table,
    allowed_operations_for_table,
    allowed_tables,
    blocked_tables,
    requires_confirmation_for_query,
)
from .row_level_security_service import RowLevelSecurityService
from .schemas import AccessPolicy, VerifiedUser, ValidationResult


TCL_COMMANDS = (
    "BEGIN",
    "START TRANSACTION",
    "COMMIT",
    "ROLLBACK",
    "SAVEPOINT",
    "RELEASE SAVEPOINT",
    "SET TRANSACTION",
)
DCL_COMMANDS = ("GRANT", "REVOKE")
DDL_COMMANDS = ("DROP", "ALTER", "TRUNCATE", "CREATE")
ADMIN_DDL_PATTERNS = (
    "CREATE DATABASE",
    "DROP DATABASE",
    "CREATE USER",
    "DROP USER",
    "CREATE ROLE",
    "DROP ROLE",
    "ALTER USER",
    "ALTER ROLE",
    "ALTER SYSTEM",
    "DROP SCHEMA",
    "CREATE SCHEMA",
    "CREATE EXTENSION",
    "FLUSH",
    "SHUTDOWN",
    "USE ",
    "ATTACH",
    "PRAGMA",
)
PRIVATE_WORKSPACE_DDL_PATTERNS = (
    "CREATE TABLE",
    "ALTER TABLE",
    "DROP TABLE",
    "CREATE INDEX",
    "CREATE VIEW",
)
DANGEROUS_TABLES = {
    "users",
    "audit_logs",
    "query_history",
    "selected_queries",
    "generated_query_options",
    "database_connections",
    "access_policies",
    "information_schema",
    "pg_catalog",
    "mysql",
    "sys",
    "performance_schema",
}
DANGEROUS_COLUMNS = {"password", "password_hash", "passwordhash"}
CONFIRMATION_REQUIRED_QUERIES = {"INSERT", "UPDATE", "DELETE"}
EXECUTABLE_CATEGORIES = {"DQL", "DML", "DDL"}
COMMAND_TO_CATEGORY = {
    "SELECT": "DQL",
    "INSERT": "DML",
    "UPDATE": "DML",
    "DELETE": "DML",
}


def classify_query(sql: str) -> str:
    command = classify_sql_command(sql)
    if command in COMMAND_TO_CATEGORY:
        return COMMAND_TO_CATEGORY[command]
    if command == "DDL":
        return "DDL"
    if command in {"DCL", "TCL"}:
        return command
    return "UNKNOWN"


def classify_sql_command(sql: str) -> str:
    cleaned = sql.strip().rstrip(";").strip()
    upper_sql = re.sub(r"\s+", " ", cleaned.upper())
    first_word = upper_sql.split(" ", 1)[0] if upper_sql else ""
    if any(upper_sql.startswith(command) for command in TCL_COMMANDS):
        return "TCL"
    if first_word in DCL_COMMANDS:
        return "DCL"
    if first_word in DDL_COMMANDS:
        return "DDL"
    if first_word in {"SELECT", "WITH"}:
        return "SELECT"
    if first_word == "INSERT":
        return "INSERT"
    if first_word == "UPDATE":
        return "UPDATE"
    if first_word == "DELETE":
        return "DELETE"
    return "UNKNOWN"


def validate_sql(sql: str, user: VerifiedUser, policies: list[AccessPolicy], dialect: str) -> ValidationResult:
    command_type = classify_sql_command(sql)
    query_type = classify_query(sql)
    errors: list[str] = []
    warnings: list[str] = []

    if _has_sql_comment(sql):
        errors.append("SQL comments are not allowed.")
    if _has_extra_semicolon(sql):
        errors.append("Only one SQL statement is allowed.")

    if query_type == "TCL":
        return ValidationResult(
            isValid=not errors,
            queryType="TCL",
            queryCategory="TCL",
            executionAllowed=False,
            requiresConfirmation=False,
            normalizedSql=sql.strip().rstrip(";") if not errors else "",
            warnings=["Transaction-control commands are explained but cannot be executed."],
            securityErrors=errors,
        )
    if query_type == "DCL":
        return ValidationResult(
            isValid=False,
            queryType="DCL",
            queryCategory="DCL",
            executionAllowed=False,
            requiresConfirmation=False,
            securityErrors=errors + ["GRANT and REVOKE are not executable because permission management is restricted."],
        )
    if query_type == "DDL":
        return _validate_private_workspace_ddl(sql, user, policies, dialect, errors)
    if query_type == "UNKNOWN":
        return ValidationResult(
            isValid=False,
            queryType="UNKNOWN",
            queryCategory="UNKNOWN",
            executionAllowed=False,
            requiresConfirmation=False,
            securityErrors=errors + ["Unknown SQL commands are blocked."],
        )

    try:
        parsed = sqlglot.parse(sql, dialect=dialect)
    except sqlglot.errors.ParseError as exc:
        return ValidationResult(
            isValid=False,
            queryType=query_type,
            queryCategory=query_type,
            executionAllowed=False,
            requiresConfirmation=False,
            securityErrors=[f"Invalid SQL syntax: {exc}"],
        )

    if len(parsed) != 1:
        errors.append("Only one SQL statement is allowed.")

    if errors:
        return ValidationResult(
            isValid=False,
            queryType=query_type,
            queryCategory=query_type,
            executionAllowed=False,
            requiresConfirmation=False,
            securityErrors=errors,
        )

    expression = parsed[0]
    referenced_tables = _referenced_tables(expression)
    referenced_columns = _referenced_columns(expression)
    policy_tables = allowed_tables(policies, user)
    allow_all_tables = all_workspace_tables_allowed(policies, user)
    blocked_policy_tables = blocked_tables(policies, user)

    structure_errors = _unsafe_structure_errors(expression, command_type)
    errors.extend(structure_errors)
    errors.extend(_qualified_reference_errors(expression))

    for table in referenced_tables:
        if table in DANGEROUS_TABLES or table in blocked_policy_tables:
            errors.append(f"Table '{table}' is blocked by policy.")
            continue
        if not allow_all_tables and table not in policy_tables:
            errors.append(f"Table '{table}' is not allowed for this user.")
            continue
        operations = allowed_operations_for_table(policies, user, table)
        if query_type not in operations and command_type not in operations:
            errors.append(f"{command_type} is not allowed on table '{table}'.")

    for column in referenced_columns:
        if column in DANGEROUS_COLUMNS:
            errors.append(f"Column '{column}' is blocked.")
            continue
        if referenced_tables and not any(_column_allowed(column, table, policies, user) for table in referenced_tables):
            errors.append(f"Column '{column}' is not allowed by policy.")

    if _uses_wildcard(expression):
        for table in referenced_tables:
            if allowed_columns_for_table(policies, user, table):
                errors.append("SELECT * is not allowed when column-level restrictions are active.")
                break
    if query_type == "INSERT" and _insert_omits_column_list(expression):
        for table in referenced_tables:
            if allowed_columns_for_table(policies, user, table):
                errors.append("INSERT must include an explicit column list when column-level restrictions are active.")
                break

    if command_type in {"UPDATE", "DELETE"} and not expression.args.get("where"):
        errors.append(f"{command_type} requires a WHERE clause.")
        warnings.append(f"{command_type} requires preview and confirmation.")
    elif command_type in {"UPDATE", "DELETE"}:
        warnings.append(f"{command_type} requires preview and confirmation.")
    elif command_type == "INSERT":
        warnings.append("INSERT requires preview and confirmation.")

    requires_confirmation = requires_confirmation_for_query(policies, user, command_type)
    normalized_sql = expression.sql(dialect=dialect).rstrip(";") if not errors else ""
    return ValidationResult(
        isValid=not errors,
        queryType=query_type,
        queryCategory=query_type,
        executionAllowed=not errors and query_type in EXECUTABLE_CATEGORIES,
        requiresConfirmation=requires_confirmation,
        normalizedSql=normalized_sql,
        warnings=warnings,
        securityErrors=errors,
    )


def enforce_row_level(sql: str, user: VerifiedUser, policies: list[AccessPolicy], dialect: str) -> tuple[str, dict[str, Any]]:
    result = RowLevelSecurityService(user, policies, dialect).enforce(sql)
    if not result.isEnforced:
        return "SELECT 1 WHERE 1 = 0", {}
    return result.finalEnforcedSql, result.parameters


def build_write_preview_sql(final_sql: str, user: VerifiedUser, policies: list[AccessPolicy], dialect: str) -> str:
    expression = sqlglot.parse_one(final_sql, dialect=dialect)
    table_name = _first_table(expression)
    where = expression.args.get("where")
    where_sql = where.this.sql(dialect=dialect) if where is not None else "1 = 0"
    allowed_columns = allowed_columns_for_table(policies, user, table_name)
    columns = ", ".join(sorted(allowed_columns)) if allowed_columns else "*"
    return f"SELECT {columns} FROM {table_name} WHERE {where_sql}"


def _validate_private_workspace_ddl(
    sql: str,
    user: VerifiedUser,
    policies: list[AccessPolicy],
    dialect: str,
    existing_errors: list[str],
) -> ValidationResult:
    errors = list(existing_errors)
    warnings: list[str] = []
    normalized_input = re.sub(r"\s+", " ", sql.strip().rstrip(";")).upper()

    if any(normalized_input.startswith(pattern) for pattern in ADMIN_DDL_PATTERNS):
        return ValidationResult(
            isValid=False,
            queryType="DDL",
            queryCategory="DDL",
            executionAllowed=False,
            requiresConfirmation=False,
            securityErrors=errors + ["Database-level administration is restricted for security."],
        )

    if not any(normalized_input.startswith(pattern) for pattern in PRIVATE_WORKSPACE_DDL_PATTERNS):
        return ValidationResult(
            isValid=False,
            queryType="DDL",
            queryCategory="DDL",
            executionAllowed=False,
            requiresConfirmation=False,
            securityErrors=errors + ["Only allow-listed table and index DDL can be considered."],
        )

    if not _category_allowed(policies, user, "DDL"):
        errors.append("DDL is not allowed by the active access policy.")

    try:
        parsed = sqlglot.parse(sql, dialect=dialect)
    except sqlglot.errors.ParseError as exc:
        return ValidationResult(
            isValid=False,
            queryType="DDL",
            queryCategory="DDL",
            executionAllowed=False,
            requiresConfirmation=False,
            securityErrors=[f"Invalid SQL syntax: {exc}"],
        )

    if len(parsed) != 1:
        errors.append("Only one SQL statement is allowed.")

    expression = parsed[0]
    errors.extend(_qualified_reference_errors(expression))

    referenced_tables = _referenced_tables(expression)
    blocked_policy_tables = blocked_tables(policies, user)
    for table in referenced_tables:
        if table in DANGEROUS_TABLES or table in blocked_policy_tables:
            errors.append(f"Table '{table}' is blocked by policy.")

    if normalized_input.startswith("DROP TABLE") and _unsafe_drop_table_reference(sql):
        errors.append("DROP TABLE allows only one simple unquoted table name in the selected database.")
    if normalized_input.startswith("ALTER TABLE") and " ADD COLUMN " not in f" {normalized_input} ":
        errors.append("Only ALTER TABLE ADD COLUMN is allowed.")

    requires_confirmation = True
    if requires_confirmation:
        warnings.append("DDL changes database structure and requires preview plus explicit confirmation.")

    return ValidationResult(
        isValid=not errors,
        queryType="DDL",
        queryCategory="DDL",
        executionAllowed=not errors,
        requiresConfirmation=requires_confirmation,
        normalizedSql=expression.sql(dialect=dialect).rstrip(";") if not errors else "",
        warnings=warnings,
        securityErrors=_dedupe_errors(errors),
    )


def _category_allowed(policies: list[AccessPolicy], user: VerifiedUser, category: str) -> bool:
    category = category.upper()
    compatible_commands = {
        "DQL": {"DQL", "SELECT"},
        "DML": {"DML", "INSERT", "UPDATE", "DELETE"},
        "DDL": {"DDL"},
    }.get(category, {category})
    for policy in policies:
        if not policy.active or policy.role.upper() != user.role.upper():
            continue
        if compatible_commands.intersection({operation.upper() for operation in policy.allowedOperations}):
            return True
    return False


def _qualified_reference_errors(expression: exp.Expression) -> list[str]:
    errors: list[str] = []
    for table in expression.find_all(exp.Table):
        qualifiers = [value.lower() for value in (table.catalog, table.db) if value]
        if qualifiers:
            errors.append("Cross-schema or cross-database access is blocked for managed cloud databases.")
    return _dedupe_errors(errors)


def _column_allowed(column: str, table: str, policies: list[AccessPolicy], user: VerifiedUser) -> bool:
    allowed_columns = allowed_columns_for_table(policies, user, table)
    return not allowed_columns or column in allowed_columns


def _referenced_tables(expression: exp.Expression) -> set[str]:
    return {table.name.lower() for table in expression.find_all(exp.Table) if table.name}


def _referenced_columns(expression: exp.Expression) -> set[str]:
    columns = set()
    for column in expression.find_all(exp.Column):
        if column.name != "*":
            columns.add(column.name.lower())
    if isinstance(expression, exp.Insert) and isinstance(expression.this, exp.Schema):
        for identifier in expression.this.expressions:
            if isinstance(identifier, exp.Identifier):
                columns.add(identifier.name.lower())
    return columns


def _unsafe_structure_errors(expression: exp.Expression, query_type: str) -> list[str]:
    errors: list[str] = []
    if list(expression.find_all(exp.Join)):
        errors.append("JOIN queries are blocked because row-level enforcement cannot be guaranteed.")
    if list(expression.find_all(exp.Union)):
        errors.append("UNION queries are blocked because row-level enforcement cannot be guaranteed.")
    if list(expression.find_all(exp.With)):
        errors.append("CTE queries are blocked because row-level enforcement cannot be guaranteed.")
    if list(expression.find_all(exp.Subquery)):
        errors.append("Nested SELECT queries are blocked because row-level enforcement cannot be guaranteed.")
    if query_type == "SELECT" and len(list(expression.find_all(exp.Select))) > 1:
        errors.append("Nested SELECT queries are blocked because row-level enforcement cannot be guaranteed.")
    if isinstance(expression, exp.Command):
        errors.append("Stored procedures and command-style SQL are blocked.")
    return _dedupe_errors(errors)


def _uses_wildcard(expression: exp.Expression) -> bool:
    return any(True for _star in expression.find_all(exp.Star))


def _insert_omits_column_list(expression: exp.Expression) -> bool:
    return isinstance(expression, exp.Insert) and not (
        isinstance(expression.this, exp.Schema) and expression.this.expressions
    )


def _dedupe_errors(errors: list[str]) -> list[str]:
    deduped: list[str] = []
    for error in errors:
        if error not in deduped:
            deduped.append(error)
    return deduped


def _first_table(expression: exp.Expression) -> str:
    table = next(expression.find_all(exp.Table), None)
    return table.name.lower() if table is not None and table.name else ""


def _has_where(expression: exp.Expression) -> bool:
    return expression.args.get("where") is not None


def _has_sql_comment(sql: str) -> bool:
    return bool(re.search(r"(--|/\*|\*/|#)", sql))


def _has_extra_semicolon(sql: str) -> bool:
    stripped = sql.strip()
    return stripped.count(";") > 1 or (";" in stripped.rstrip(";"))


def _unsafe_drop_table_reference(sql: str) -> bool:
    stripped = sql.strip().rstrip(";").strip()
    match = re.fullmatch(r"DROP\s+TABLE\s+([A-Za-z_][A-Za-z0-9_]*)", stripped, flags=re.IGNORECASE)
    return match is None
