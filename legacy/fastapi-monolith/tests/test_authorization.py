"""Tests for role-based access control helpers."""

from types import SimpleNamespace

from backend.authorization import (
    can_access_column,
    can_access_row,
    can_access_table,
    can_execute_query_type,
    get_allowed_tables,
    get_row_level_rule,
)


def make_user(**overrides):
    values = {
        "user_id": 100,
        "role": "employee",
        "department": "IT",
        "employee_id": 6,
        "student_id": None,
    }
    values.update(overrides)
    return SimpleNamespace(**values)


def test_employee_cannot_read_another_employee_record() -> None:
    employee = make_user(role="employee", employee_id=6)

    assert can_access_row(employee, "Employee", {"employee_id": 6})
    assert not can_access_row(employee, "Employee", {"employee_id": 7})


def test_student_cannot_read_another_student_record() -> None:
    student = make_user(role="student", student_id=1, employee_id=None)

    assert can_access_row(student, "Students", {"student_id": 1})
    assert not can_access_row(student, "Students", {"student_id": 2})


def test_manager_cannot_view_records_from_another_department() -> None:
    manager = make_user(role="manager", department="IT", employee_id=1)

    assert can_access_row(manager, "employees", {"department": "IT"})
    assert not can_access_row(manager, "employees", {"department": "HR"})


def test_manager_cannot_delete_records() -> None:
    manager = make_user(role="manager", department="IT")

    assert can_execute_query_type(manager, "SELECT")
    assert can_execute_query_type(manager, "UPDATE")
    assert not can_execute_query_type(manager, "DELETE")


def test_employee_cannot_update_salary() -> None:
    employee = make_user(role="employee", employee_id=6)

    assert can_access_column(employee, "Employee", "salary")
    assert not can_execute_query_type(employee, "UPDATE")


def test_admin_can_access_all_rows() -> None:
    admin = make_user(role="admin", department=None, employee_id=None)

    assert get_allowed_tables(admin) == ["employees", "students"]
    assert can_access_table(admin, "Employee")
    assert can_access_table(admin, "Students")
    assert can_access_row(admin, "Employee", {"employee_id": 999, "department": "Legal"})
    assert can_access_row(admin, "Students", {"student_id": 999, "faculty_id": 500})
    assert can_execute_query_type(admin, "SELECT")
    assert can_execute_query_type(admin, "INSERT")
    assert can_execute_query_type(admin, "UPDATE")
    assert can_execute_query_type(admin, "DELETE")


def test_faculty_can_access_only_assigned_students() -> None:
    faculty = make_user(role="faculty", user_id=2, employee_id=None)

    rule = get_row_level_rule(faculty, "Students")

    assert rule["column"] == "faculty_id"
    assert rule["value"] == 2
    assert can_access_row(faculty, "Students", {"faculty_id": 2})
    assert not can_access_row(faculty, "Students", {"faculty_id": 3})

