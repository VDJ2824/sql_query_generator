"""Tests for sqlglot-backed SQL validation."""

from types import SimpleNamespace

from backend.sql_validator import (
    classify_query,
    is_select_only,
    normalize_sql,
    validate_allowed_tables_and_columns,
    validate_query_security,
    validate_single_statement,
    validate_sql_syntax,
)


def user(role: str, **overrides):
    values = {
        "role": role,
        "user_id": 1,
        "department": "IT",
        "employee_id": 6,
        "student_id": 1,
    }
    values.update(overrides)
    return SimpleNamespace(**values)


def test_classify_query_types() -> None:
    assert classify_query("SELECT * FROM employees") == "SELECT"
    assert classify_query("INSERT INTO employees (name) VALUES ('A')") == "INSERT"
    assert classify_query("UPDATE employees SET salary = 1") == "UPDATE"
    assert classify_query("DELETE FROM employees WHERE employee_id = 1") == "DELETE"
    assert classify_query("COMMIT") == "TCL"
    assert classify_query("GRANT SELECT ON employees TO user") == "DCL"
    assert classify_query("DROP TABLE employees") == "DDL"
    assert classify_query("EXPLAIN QUERY PLAN SELECT 1") == "UNKNOWN"


def test_validate_sql_syntax_and_normalize() -> None:
    result = validate_sql_syntax("select name from employees where department = 'IT';")

    assert result["is_valid"]
    assert result["query_type"] == "SELECT"
    assert normalize_sql("select name from employees") == "SELECT name FROM employees"


def test_validate_single_statement_rejects_multiple_statements_and_comments() -> None:
    multi = validate_single_statement("SELECT * FROM employees; SELECT * FROM students;")
    commented = validate_single_statement("SELECT * FROM employees -- bypass")

    assert not multi["is_valid"]
    assert "Only one SQL statement is allowed." in multi["security_errors"]
    assert not commented["is_valid"]
    assert "SQL comments are not allowed because they can bypass security checks." in commented["security_errors"]


def test_select_allowed_after_authorization() -> None:
    result = validate_query_security("SELECT employee_id, name FROM employees", user("admin"))

    assert result == {
        "is_valid": True,
        "query_type": "SELECT",
        "execution_allowed": True,
        "requires_confirmation": False,
        "normalized_sql": "SELECT employee_id, name FROM employees",
        "warnings": [],
        "security_errors": [],
    }


def test_insert_allowed_only_for_admin() -> None:
    admin_result = validate_query_security(
        "INSERT INTO students (student_id, name, email, course, cgpa) VALUES (99, 'A', 'a@example.com', 'CS', 9.1)",
        user("admin"),
    )
    employee_result = validate_query_security(
        "INSERT INTO employees (employee_id, name, email, department, salary, joining_date) "
        "VALUES (99, 'A', 'a@example.com', 'IT', 1, '2024-01-01')",
        user("employee"),
    )

    assert admin_result["is_valid"]
    assert admin_result["execution_allowed"]
    assert not employee_result["is_valid"]
    assert not employee_result["execution_allowed"]


def test_update_requires_where_and_confirmation() -> None:
    no_where = validate_query_security("UPDATE employees SET salary = 10", user("admin"))
    scoped_manager = validate_query_security(
        "UPDATE employees SET salary = salary * 1.05 WHERE department = 'IT'",
        user("manager", department="IT"),
    )

    assert not no_where["is_valid"]
    assert "UPDATE queries must include a WHERE clause." in no_where["security_errors"]
    assert scoped_manager["is_valid"]
    assert scoped_manager["execution_allowed"]
    assert scoped_manager["requires_confirmation"]


def test_manager_update_must_be_department_scoped() -> None:
    result = validate_query_security(
        "UPDATE employees SET salary = salary * 1.05 WHERE employee_id = 6",
        user("manager", department="IT"),
    )

    assert not result["is_valid"]
    assert "Manager UPDATE queries must be scoped to their own department." in result["security_errors"]


def test_delete_allowed_only_for_admin_with_where() -> None:
    no_where = validate_query_security("DELETE FROM employees", user("admin"))
    employee_delete = validate_query_security("DELETE FROM employees WHERE employee_id = 6", user("employee"))
    admin_delete = validate_query_security("DELETE FROM employees WHERE employee_id = 6", user("admin"))

    assert not no_where["is_valid"]
    assert "DELETE queries must include a WHERE clause." in no_where["security_errors"]
    assert not employee_delete["is_valid"]
    assert not employee_delete["execution_allowed"]
    assert admin_delete["is_valid"]
    assert admin_delete["requires_confirmation"]


def test_tcl_is_view_only() -> None:
    result = validate_query_security("ROLLBACK", user("admin"))

    assert result["is_valid"]
    assert result["query_type"] == "TCL"
    assert not result["execution_allowed"]
    assert result["warnings"]


def test_dcl_is_fully_blocked_without_executable_sql() -> None:
    result = validate_query_security("GRANT SELECT ON employees TO analyst", user("admin"))

    assert not result["is_valid"]
    assert result["query_type"] == "DCL"
    assert result["normalized_sql"] == ""
    assert "Permission changes are not allowed. DCL commands are fully blocked." in result["security_errors"]


def test_ddl_is_fully_blocked() -> None:
    result = validate_query_security("DROP TABLE employees", user("admin"))

    assert not result["is_valid"]
    assert result["query_type"] == "DDL"
    assert result["normalized_sql"] == ""
    assert "Schema changes are not allowed. DDL commands are fully blocked." in result["security_errors"]


def test_restricted_tables_and_columns_are_rejected() -> None:
    table_result = validate_allowed_tables_and_columns("SELECT username FROM users", user("admin"))
    column_result = validate_allowed_tables_and_columns("SELECT password_hash FROM users", user("admin"))

    assert not table_result["is_valid"]
    assert "Table 'users' is not allowed for this user." in table_result["security_errors"]
    assert not column_result["is_valid"]
    assert "Column 'password_hash' is restricted." in column_result["security_errors"]


def test_unsafe_joins_and_unions_are_rejected() -> None:
    join_result = validate_query_security(
        "SELECT employees.employee_id FROM employees JOIN students ON students.student_id = employees.employee_id",
        user("admin"),
    )
    union_result = validate_query_security(
        "SELECT employee_id FROM employees UNION SELECT student_id FROM students",
        user("admin"),
    )

    assert not join_result["is_valid"]
    assert "JOIN and UNION queries are not allowed because they can bypass row-level security." in join_result["security_errors"]
    assert not union_result["is_valid"]
    assert "JOIN and UNION queries are not allowed because they can bypass row-level security." in union_result["security_errors"]


def test_unknown_query_type_is_blocked() -> None:
    result = validate_query_security("EXPLAIN QUERY PLAN SELECT * FROM employees", user("admin"))

    assert not result["is_valid"]
    assert result["query_type"] == "UNKNOWN"
    assert "Unknown query types are not allowed." in result["security_errors"]


def test_is_select_only_compatibility_wrapper() -> None:
    allowed, _ = is_select_only("SELECT employee_id FROM employees")
    blocked, _ = is_select_only("UPDATE employees SET name = 'x'")

    assert allowed
    assert not blocked
