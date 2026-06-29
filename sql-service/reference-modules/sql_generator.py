"""Natural-language-to-SQL generation helpers."""

from __future__ import annotations

import json
import os
import re
from typing import Any

from .authorization import can_execute_query_type


QUERY_OPTION_KEYS = {
    "option_id",
    "title",
    "sql",
    "query_type",
    "tables_used",
    "columns_used",
    "explanation",
    "risk_level",
    "execution_allowed",
    "requires_confirmation",
    "warnings",
}


def build_sql_prompt(user_prompt: str, current_user: Any, accessible_schema: dict[str, Any]) -> str:
    """Create a strict JSON-only prompt for the Gemini API."""
    return (
        "You generate SQL options for a secure FastAPI backend.\n"
        "Return only valid JSON. Do not include markdown or commentary.\n"
        "The JSON must match this exact shape:\n"
        '{"user_prompt":"","query_options":[{"option_id":1,"title":"","sql":"",'
        '"query_type":"","tables_used":[],"columns_used":[],"explanation":"",'
        '"risk_level":"","execution_allowed":true,"requires_confirmation":false,"warnings":[]}]}\n\n'
        "Rules:\n"
        "- Generate 2 or 3 meaningfully different SQL alternatives when possible.\n"
        "- Use only the allowed tables and columns provided below.\n"
        "- Never invent table names or column names.\n"
        "- Never include password_hash.\n"
        "- Respect row-level restrictions in every SQL option.\n"
        "- Never execute SQL.\n"
        "- If unsafe, return a safe explanation option with empty SQL.\n\n"
        f"User role: {getattr(current_user, 'role', '')}\n"
        f"User id: {getattr(current_user, 'user_id', '')}\n"
        f"Employee id: {getattr(current_user, 'employee_id', '')}\n"
        f"Student id: {getattr(current_user, 'student_id', '')}\n"
        f"Department: {getattr(current_user, 'department', '')}\n"
        f"Allowed schema: {json.dumps(accessible_schema)}\n"
        f"User request: {user_prompt}\n"
    )


def call_gemini_for_sql_options(prompt: str) -> dict[str, Any] | None:
    """Call Gemini and parse the JSON response."""
    api_key = os.getenv("GEMINI_API_KEY")
    if not api_key or api_key.startswith("your_"):
        return None

    try:
        import google.generativeai as genai

        genai.configure(api_key=api_key)
        model = genai.GenerativeModel(os.getenv("GEMINI_MODEL", "gemini-1.5-flash"))
        response = model.generate_content(
            prompt,
            generation_config={
                "temperature": 0.2,
                "response_mime_type": "application/json",
            },
        )
        content = getattr(response, "text", "") or "{}"
        return _parse_json_content(content)
    except Exception:
        return None


def generate_sql_options(
    user_prompt: str,
    current_user: Any,
    accessible_schema: dict[str, Any],
) -> dict[str, Any]:
    """Generate SQL options with Gemini, falling back to rules when needed."""
    prompt = build_sql_prompt(user_prompt, current_user, accessible_schema)
    ai_payload = call_gemini_for_sql_options(prompt)
    if ai_payload:
        return normalize_generation_response(ai_payload, user_prompt, current_user, accessible_schema)
    return fallback_generate_sql_options(user_prompt, current_user, accessible_schema)


def _parse_json_content(content: str) -> dict[str, Any]:
    """Parse JSON content, tolerating accidental markdown code fences."""
    cleaned = content.strip()
    if cleaned.startswith("```"):
        cleaned = re.sub(r"^```(?:json)?", "", cleaned, flags=re.IGNORECASE).strip()
        cleaned = re.sub(r"```$", "", cleaned).strip()
    return json.loads(cleaned)


def normalize_generation_response(
    payload: dict[str, Any],
    user_prompt: str,
    current_user: Any,
    accessible_schema: dict[str, Any],
) -> dict[str, Any]:
    """Keep only the exact fields the frontend is allowed to receive."""
    allowed_tables = _allowed_table_names(accessible_schema)
    allowed_columns = _allowed_column_names(accessible_schema)
    options = []

    for index, option in enumerate(payload.get("query_options", []), start=1):
        if not isinstance(option, dict):
            continue
        query_type = str(option.get("query_type", "SELECT")).upper()
        tables_used = [table for table in option.get("tables_used", []) if table in allowed_tables]
        columns_used = [
            column
            for column in option.get("columns_used", [])
            if column in allowed_columns and column != "password_hash"
        ]
        sql = str(option.get("sql", ""))
        warnings = list(option.get("warnings", []))
        safe_sql = _sql_references_only_allowed_names(sql, allowed_tables, allowed_columns)
        execution_allowed = bool(option.get("execution_allowed", True)) and can_execute_query_type(
            current_user,
            query_type,
        )

        if not safe_sql:
            sql = ""
            execution_allowed = False
            warnings.append("Generated SQL referenced a table or column outside the allowed schema.")

        options.append(
            _make_option(
                option_id=int(option.get("option_id", index)),
                title=str(option.get("title", "Generated option")),
                sql=sql,
                query_type=query_type,
                tables_used=tables_used,
                columns_used=columns_used,
                explanation=str(option.get("explanation", "")),
                risk_level=str(option.get("risk_level", _risk_level(query_type))),
                execution_allowed=execution_allowed,
                requires_confirmation=bool(option.get("requires_confirmation", query_type != "SELECT")),
                warnings=warnings,
            )
        )

    if not options:
        return _safe_response(user_prompt, "The AI response did not contain safe query options.")

    return {"user_prompt": user_prompt, "query_options": options[:3]}


def fallback_generate_sql_options(
    user_prompt: str,
    current_user: Any,
    accessible_schema: dict[str, Any],
) -> dict[str, Any]:
    """Rule-based generator for common beginner test prompts."""
    prompt = user_prompt.lower()
    options: list[dict[str, Any]] = []

    if "update" in prompt and "salary" in prompt:
        options.extend(_update_salary_options(user_prompt, current_user, accessible_schema))
    elif "delete" in prompt:
        options.extend(_delete_options(user_prompt, current_user, accessible_schema))
    elif "group" in prompt and "department" in prompt and _has_table(accessible_schema, "Employee"):
        options.extend(_group_by_department_options(current_user, accessible_schema))
    elif "salary" in prompt and _has_column(accessible_schema, "Employee", "salary"):
        options.extend(_salary_options(user_prompt, current_user, accessible_schema))
    elif "cgpa" in prompt and _has_table(accessible_schema, "Students"):
        options.extend(_top_cgpa_options(user_prompt, current_user, accessible_schema))
    elif "department" in prompt and _has_table(accessible_schema, "Employee"):
        options.extend(_department_options(user_prompt, current_user, accessible_schema))
    elif "count" in prompt:
        options.extend(_count_options(current_user, accessible_schema))

    if not options:
        return _safe_response(
            user_prompt,
            "This request could not be safely converted into SQL from the allowed schema.",
        )

    return {"user_prompt": user_prompt, "query_options": options[:3]}


def _salary_options(user_prompt: str, current_user: Any, accessible_schema: dict[str, Any]) -> list[dict[str, Any]]:
    value = _first_number(user_prompt) or "70000"
    where = _with_row_rule(current_user, "Employee", f"salary > {value}")
    return [
        _select_option(
            1,
            "Detailed salary records",
            f"SELECT employee_id, name, email, department, salary, joining_date FROM employees WHERE {where};",
            ["employee_id", "name", "email", "department", "salary", "joining_date"],
            "Shows detailed Employee rows above the requested salary.",
        ),
        _select_option(
            2,
            "Basic salary list",
            f"SELECT name, department, salary FROM employees WHERE {where};",
            ["name", "department", "salary"],
            "Shows a compact list with only the most useful fields.",
        ),
        _select_option(
            3,
            "Salary count summary",
            f"SELECT COUNT(*) AS matching_employees FROM employees WHERE {where};",
            ["salary"],
            "Counts matching Employee rows without listing individual records.",
        ),
    ]


def _top_cgpa_options(user_prompt: str, current_user: Any, accessible_schema: dict[str, Any]) -> list[dict[str, Any]]:
    limit = _first_int(user_prompt) or 5
    where = _row_rule_condition(current_user, "Students")
    suffix = f" WHERE {where}" if where else ""
    return [
        _select_option(
            1,
            "Top students by CGPA",
            f"SELECT student_id, name, email, course, cgpa FROM students{suffix} ORDER BY cgpa DESC LIMIT {limit};",
            ["student_id", "name", "email", "course", "cgpa"],
            "Shows the highest CGPA student records allowed for the current user.",
            tables=["Students"],
        ),
        _select_option(
            2,
            "Names and CGPA only",
            f"SELECT name, course, cgpa FROM students{suffix} ORDER BY cgpa DESC LIMIT {limit};",
            ["name", "course", "cgpa"],
            "Shows a simpler ranking with fewer columns.",
            tables=["Students"],
        ),
    ]


def _department_options(user_prompt: str, current_user: Any, accessible_schema: dict[str, Any]) -> list[dict[str, Any]]:
    department = _department_from_prompt(user_prompt) or getattr(current_user, "department", None) or "IT"
    where = _with_row_rule(current_user, "Employee", f"department = '{_escape_sql_literal(department)}'")
    return [
        _select_option(
            1,
            "Department employee details",
            f"SELECT employee_id, name, email, department, salary, joining_date FROM employees WHERE {where};",
            ["employee_id", "name", "email", "department", "salary", "joining_date"],
            "Shows detailed Employee rows for the requested department.",
        ),
        _select_option(
            2,
            "Department count",
            f"SELECT department, COUNT(*) AS employee_count FROM employees WHERE {where} GROUP BY department;",
            ["department"],
            "Summarizes how many Employee rows match the department filter.",
        ),
    ]


def _count_options(current_user: Any, accessible_schema: dict[str, Any]) -> list[dict[str, Any]]:
    options = []
    if _has_table(accessible_schema, "Employee"):
        where = _row_rule_condition(current_user, "Employee")
        suffix = f" WHERE {where}" if where else ""
        options.append(
            _select_option(
                1,
                "Count employees",
                f"SELECT COUNT(*) AS employee_count FROM employees{suffix};",
                [],
                "Counts Employee rows available to the current user.",
            )
        )
    if _has_table(accessible_schema, "Students"):
        where = _row_rule_condition(current_user, "Students")
        suffix = f" WHERE {where}" if where else ""
        options.append(
            _select_option(
                len(options) + 1,
                "Count students",
                f"SELECT COUNT(*) AS student_count FROM students{suffix};",
                [],
                "Counts Students rows available to the current user.",
                tables=["Students"],
            )
        )
    return options


def _group_by_department_options(current_user: Any, accessible_schema: dict[str, Any]) -> list[dict[str, Any]]:
    where = _row_rule_condition(current_user, "Employee")
    suffix = f" WHERE {where}" if where else ""
    return [
        _select_option(
            1,
            "Employees grouped by department",
            f"SELECT department, COUNT(*) AS employee_count FROM employees{suffix} GROUP BY department;",
            ["department"],
            "Groups accessible Employee rows by department.",
        )
    ]


def _update_salary_options(user_prompt: str, current_user: Any, accessible_schema: dict[str, Any]) -> list[dict[str, Any]]:
    percent = _first_number(user_prompt) or "5"
    allowed = can_execute_query_type(current_user, "UPDATE") and _has_column(accessible_schema, "Employee", "salary")
    where = _row_rule_condition(current_user, "Employee")
    if not allowed or not where:
        return [
            _make_option(
                1,
                "Salary update not allowed",
                "",
                "UPDATE",
                ["Employee"],
                ["salary"],
                "This role cannot safely update salary records.",
                "high",
                False,
                True,
                ["UPDATE is not permitted for this role or lacks a safe row restriction."],
            )
        ]
    return [
        _make_option(
            1,
            "Preview salary update",
            f"SELECT employee_id, name, salary, salary * (1 + {percent} / 100.0) AS new_salary FROM employees WHERE {where};",
            "SELECT",
            ["Employee"],
            ["employee_id", "name", "salary"],
            "Preview the salary changes before any UPDATE is considered.",
            "medium",
            True,
            False,
            [],
        ),
        _make_option(
            2,
            "Confirmed salary update",
            f"UPDATE employees SET salary = salary * (1 + {percent} / 100.0) WHERE {where};",
            "UPDATE",
            ["Employee"],
            ["salary"],
            "Updates salary only inside the enforced row-level scope after confirmation.",
            "high",
            True,
            True,
            ["Must be previewed and explicitly confirmed before execution."],
        ),
    ]


def _delete_options(user_prompt: str, current_user: Any, accessible_schema: dict[str, Any]) -> list[dict[str, Any]]:
    allowed = can_execute_query_type(current_user, "DELETE")
    table = "Employee" if _has_table(accessible_schema, "Employee") else "Students"
    return [
        _make_option(
            1,
            "Delete request review",
            "" if not allowed else f"-- DELETE requires validation and a specific safe condition for {table}.",
            "DELETE",
            [table],
            [],
            "DELETE requests require strict validation and confirmation before execution.",
            "high",
            allowed,
            True,
            ["This endpoint never executes DELETE statements."],
        )
    ]


def _select_option(
    option_id: int,
    title: str,
    sql: str,
    columns: list[str],
    explanation: str,
    tables: list[str] | None = None,
) -> dict[str, Any]:
    return _make_option(
        option_id,
        title,
        sql,
        "SELECT",
        tables or ["Employee"],
        columns,
        explanation,
        "low",
        True,
        False,
        [],
    )


def _make_option(
    option_id: int,
    title: str,
    sql: str,
    query_type: str,
    tables_used: list[str],
    columns_used: list[str],
    explanation: str,
    risk_level: str,
    execution_allowed: bool,
    requires_confirmation: bool,
    warnings: list[str],
) -> dict[str, Any]:
    return {
        "option_id": option_id,
        "title": title,
        "sql": sql,
        "query_type": query_type,
        "tables_used": tables_used,
        "columns_used": columns_used,
        "explanation": explanation,
        "risk_level": risk_level,
        "execution_allowed": execution_allowed,
        "requires_confirmation": requires_confirmation,
        "warnings": warnings,
    }


def _safe_response(user_prompt: str, explanation: str) -> dict[str, Any]:
    return {
        "user_prompt": user_prompt,
        "query_options": [
            _make_option(
                1,
                "Request cannot be safely fulfilled",
                "",
                "UNKNOWN",
                [],
                [],
                explanation,
                "low",
                False,
                False,
                ["No SQL was generated."],
            )
        ],
    }


def _allowed_table_names(accessible_schema: dict[str, Any]) -> set[str]:
    names = set()
    for table in accessible_schema.get("allowed_tables", []):
        label = table["table_name"]
        names.add(label)
        names.add(_sql_table_name(label))
    return names


def _allowed_column_names(accessible_schema: dict[str, Any]) -> set[str]:
    return {
        column["name"]
        for table in accessible_schema.get("allowed_tables", [])
        for column in table.get("allowed_columns", [])
    }


def _has_table(accessible_schema: dict[str, Any], table_name: str) -> bool:
    return table_name in {table["table_name"] for table in accessible_schema.get("allowed_tables", [])}


def _has_column(accessible_schema: dict[str, Any], table_name: str, column_name: str) -> bool:
    for table in accessible_schema.get("allowed_tables", []):
        if table["table_name"] == table_name:
            return column_name in {column["name"] for column in table.get("allowed_columns", [])}
    return False


def _sql_table_name(table_label: str) -> str:
    return {"Employee": "employees", "Students": "students"}.get(table_label, table_label)


def _row_rule_condition(current_user: Any, table_name: str) -> str:
    role = str(getattr(current_user, "role", "")).lower()
    if role == "admin":
        return ""
    if role == "manager" and table_name == "Employee":
        department = _escape_sql_literal(getattr(current_user, "department", ""))
        return f"department = '{department}'"
    if role == "employee" and table_name == "Employee":
        return f"employee_id = {int(getattr(current_user, 'employee_id', 0) or 0)}"
    if role == "faculty" and table_name == "Students":
        return f"faculty_id = {int(getattr(current_user, 'user_id', 0) or 0)}"
    if role == "student" and table_name == "Students":
        return f"student_id = {int(getattr(current_user, 'student_id', 0) or 0)}"
    return "1 = 0"


def _with_row_rule(current_user: Any, table_name: str, condition: str) -> str:
    row_rule = _row_rule_condition(current_user, table_name)
    if not row_rule:
        return condition
    return f"({condition}) AND ({row_rule})"


def _first_number(prompt: str) -> str | None:
    match = re.search(r"\d+(?:\.\d+)?", prompt)
    return match.group(0) if match else None


def _first_int(prompt: str) -> int | None:
    match = re.search(r"\d+", prompt)
    return int(match.group(0)) if match else None


def _department_from_prompt(prompt: str) -> str | None:
    departments = ["IT", "HR", "Finance", "Sales", "Operations"]
    lowered = prompt.lower()
    for department in departments:
        if department.lower() in lowered:
            return department
    return None


def _escape_sql_literal(value: Any) -> str:
    return str(value).replace("'", "''")


def _risk_level(query_type: str) -> str:
    return "low" if query_type == "SELECT" else "high"


def _sql_references_only_allowed_names(sql: str, allowed_tables: set[str], allowed_columns: set[str]) -> bool:
    lowered = sql.lower()
    if "password_hash" in lowered:
        return False
    blocked_tables = {"users", "query_history", "audit_logs"}
    if any(table in lowered for table in blocked_tables):
        return False
    referenced_tables = set(re.findall(r"\b(?:from|join|update|into)\s+([a-zA-Z_][\w]*)", lowered))
    if not referenced_tables:
        return True
    return referenced_tables.issubset({table.lower() for table in allowed_tables})
