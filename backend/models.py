"""SQLAlchemy models for the secure AI SQL query generator project."""

from __future__ import annotations

from sqlalchemy import Column, Date, DateTime, Float, ForeignKey, Integer, String, Text, func
from sqlalchemy.orm import relationship

from .database import Base


class User(Base):
    __tablename__ = "users"

    user_id = Column(Integer, primary_key=True, index=True)
    username = Column(String(100), unique=True, nullable=False, index=True)
    password_hash = Column(String(255), nullable=False)
    role = Column(String(50), nullable=False)
    department = Column(String(100), nullable=True)
    employee_id = Column(Integer, ForeignKey("employees.employee_id"), nullable=True)
    student_id = Column(Integer, ForeignKey("students.student_id"), nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)

    employee = relationship("Employee", foreign_keys=[employee_id], lazy="joined")
    student = relationship("Student", foreign_keys=[student_id], lazy="joined")


class Employee(Base):
    __tablename__ = "employees"

    employee_id = Column(Integer, primary_key=True, index=True)
    name = Column(String(150), nullable=False)
    email = Column(String(255), unique=True, nullable=False, index=True)
    department = Column(String(100), nullable=False)
    salary = Column(Float, nullable=False)
    joining_date = Column(Date, nullable=False)
    manager_id = Column(Integer, ForeignKey("employees.employee_id"), nullable=True)

    manager = relationship("Employee", remote_side=[employee_id], lazy="joined")


class Student(Base):
    __tablename__ = "students"

    student_id = Column(Integer, primary_key=True, index=True)
    name = Column(String(150), nullable=False)
    email = Column(String(255), unique=True, nullable=False, index=True)
    course = Column(String(120), nullable=False)
    cgpa = Column(Float, nullable=False)
    faculty_id = Column(Integer, nullable=True)


class QueryHistory(Base):
    __tablename__ = "query_history"

    history_id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.user_id"), nullable=False)
    user_prompt = Column(Text, nullable=False)
    selected_option_id = Column(Integer, nullable=True)
    generated_sql = Column(Text, nullable=False)
    final_enforced_sql = Column(Text, nullable=False)
    query_type = Column(String(80), nullable=False)
    execution_status = Column(String(50), nullable=False)
    rows_affected = Column(Integer, nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)


class SelectedQueries(Base):
    __tablename__ = "selected_queries"

    selected_query_id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.user_id"), nullable=False, index=True)
    option_id = Column(Integer, nullable=False)
    title = Column(String(255), nullable=False)
    generated_sql = Column(Text, nullable=False)
    query_type = Column(String(80), nullable=False)
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    expires_at = Column(DateTime(timezone=True), nullable=False)


class AuditLogs(Base):
    __tablename__ = "audit_logs"

    log_id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.user_id"), nullable=False)
    action_type = Column(String(80), nullable=False)
    user_prompt = Column(Text, nullable=True)
    generated_sql = Column(Text, nullable=True)
    final_enforced_sql = Column(Text, nullable=True)
    query_type = Column(String(80), nullable=True)
    execution_status = Column(String(50), nullable=False)
    rows_affected = Column(Integer, nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
