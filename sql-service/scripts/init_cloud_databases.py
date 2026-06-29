"""Initialize managed Neon PostgreSQL and TiDB/MySQL demo databases.

This script is intentionally separate from app startup. Run it only when you
want to create or refresh the college-demo relational tables in managed cloud
databases.
"""

from __future__ import annotations

import argparse
import os
import sys
from pathlib import Path

from sqlalchemy import create_engine, text


PROJECT_ROOT = Path(__file__).resolve().parents[2]
SQL_SERVICE_ROOT = PROJECT_ROOT / "sql-service"
if str(SQL_SERVICE_ROOT) not in sys.path:
    sys.path.insert(0, str(SQL_SERVICE_ROOT))

from app.env_loader import load_environment  # noqa: E402

DEPARTMENTS = [
    (1, "IT", "Bengaluru"),
    (2, "HR", "Mumbai"),
    (3, "Finance", "Delhi"),
    (4, "Sales", "Pune"),
    (5, "Operations", "Hyderabad"),
]

EMPLOYEES = [
    (1, "Aarav Sharma", "aarav.sharma@example.com", "IT", 82000, "2021-04-12"),
    (2, "Diya Mehta", "diya.mehta@example.com", "HR", 54000, "2020-08-03"),
    (3, "Kabir Rao", "kabir.rao@example.com", "Finance", 76000, "2019-02-18"),
    (4, "Ananya Iyer", "ananya.iyer@example.com", "Sales", 61000, "2022-01-24"),
    (5, "Rohan Gupta", "rohan.gupta@example.com", "Operations", 59000, "2023-03-11"),
    (6, "Ishita Nair", "ishita.nair@example.com", "IT", 91000, "2018-07-09"),
    (7, "Vivaan Kapoor", "vivaan.kapoor@example.com", "HR", 48000, "2021-11-15"),
    (8, "Meera Joshi", "meera.joshi@example.com", "Finance", 70000, "2020-05-29"),
    (9, "Arjun Menon", "arjun.menon@example.com", "Sales", 65000, "2019-10-06"),
    (10, "Sara Khan", "sara.khan@example.com", "Operations", 57000, "2022-09-20"),
    (11, "Neil Thomas", "neil.thomas@example.com", "IT", 99000, "2017-12-04"),
    (12, "Tara Singh", "tara.singh@example.com", "HR", 52000, "2023-06-01"),
    (13, "Dev Patel", "dev.patel@example.com", "Finance", 83000, "2018-01-16"),
    (14, "Nisha Verma", "nisha.verma@example.com", "Sales", 68000, "2021-03-08"),
    (15, "Karan Bhat", "karan.bhat@example.com", "Operations", 62000, "2020-12-14"),
    (16, "Priya Das", "priya.das@example.com", "IT", 88000, "2022-04-19"),
    (17, "Aditya Bose", "aditya.bose@example.com", "HR", 51000, "2019-09-23"),
    (18, "Maya Pillai", "maya.pillai@example.com", "Finance", 79000, "2021-07-27"),
    (19, "Yash Jain", "yash.jain@example.com", "Sales", 72000, "2023-02-10"),
    (20, "Riya Sen", "riya.sen@example.com", "Operations", 60000, "2018-06-30"),
    (21, "Om Kulkarni", "om.kulkarni@example.com", "IT", 94000, "2020-10-22"),
    (22, "Sneha Roy", "sneha.roy@example.com", "HR", 56000, "2022-08-17"),
    (23, "Harsh Malhotra", "harsh.malhotra@example.com", "Finance", 74000, "2023-01-05"),
    (24, "Aisha Ali", "aisha.ali@example.com", "Sales", 69000, "2017-05-13"),
    (25, "Manav Saxena", "manav.saxena@example.com", "Operations", 63000, "2021-12-21"),
]

STUDENTS = [
    (1, "Aditi Sharma", "aditi.sharma@example.com", "Computer Science", 9.1, 101),
    (2, "Rahul Mehta", "rahul.mehta@example.com", "Data Science", 8.6, 102),
    (3, "Simran Kaur", "simran.kaur@example.com", "Cybersecurity", 8.9, 103),
    (4, "Vikram Rao", "vikram.rao@example.com", "AI and ML", 9.3, 101),
    (5, "Pooja Nair", "pooja.nair@example.com", "Information Systems", 7.8, 102),
    (6, "Nikhil Gupta", "nikhil.gupta@example.com", "Computer Science", 8.2, 103),
    (7, "Kavya Iyer", "kavya.iyer@example.com", "Data Science", 9.5, 101),
    (8, "Ritvik Jain", "ritvik.jain@example.com", "Cybersecurity", 7.9, 102),
    (9, "Mansi Verma", "mansi.verma@example.com", "AI and ML", 8.7, 103),
    (10, "Ishan Das", "ishan.das@example.com", "Information Systems", 8.1, 101),
    (11, "Tanvi Roy", "tanvi.roy@example.com", "Computer Science", 9.0, 102),
    (12, "Aryan Bose", "aryan.bose@example.com", "Data Science", 7.6, 103),
    (13, "Neha Patel", "neha.patel@example.com", "Cybersecurity", 8.4, 101),
    (14, "Samar Khan", "samar.khan@example.com", "AI and ML", 9.2, 102),
    (15, "Rhea Menon", "rhea.menon@example.com", "Information Systems", 8.0, 103),
    (16, "Kunal Singh", "kunal.singh@example.com", "Computer Science", 8.8, 101),
    (17, "Anika Joshi", "anika.joshi@example.com", "Data Science", 9.4, 102),
    (18, "Dhruv Kapoor", "dhruv.kapoor@example.com", "Cybersecurity", 7.7, 103),
    (19, "Sana Ali", "sana.ali@example.com", "AI and ML", 8.5, 101),
    (20, "Pranav Bhat", "pranav.bhat@example.com", "Information Systems", 8.3, 102),
    (21, "Esha Pillai", "esha.pillai@example.com", "Computer Science", 9.6, 103),
    (22, "Yuvraj Sen", "yuvraj.sen@example.com", "Data Science", 7.5, 101),
    (23, "Lavanya Das", "lavanya.das@example.com", "Cybersecurity", 8.9, 102),
    (24, "Reyansh Roy", "reyansh.roy@example.com", "AI and ML", 8.6, 103),
    (25, "Myra Thomas", "myra.thomas@example.com", "Information Systems", 9.1, 101),
]


def statements_for(target: str) -> list[str]:
    if target == "postgres":
        return [
            """
            CREATE TABLE IF NOT EXISTS Department (
              department_id INTEGER PRIMARY KEY,
              department_name VARCHAR(100) NOT NULL,
              location VARCHAR(100) NOT NULL
            )
            """,
            """
            CREATE TABLE IF NOT EXISTS Employee (
              employee_id INTEGER PRIMARY KEY,
              name VARCHAR(120) NOT NULL,
              email VARCHAR(160) UNIQUE NOT NULL,
              department VARCHAR(100) NOT NULL,
              salary NUMERIC(12, 2) NOT NULL,
              joining_date DATE NOT NULL
            )
            """,
            """
            CREATE TABLE IF NOT EXISTS Students (
              student_id INTEGER PRIMARY KEY,
              name VARCHAR(120) NOT NULL,
              email VARCHAR(160) UNIQUE NOT NULL,
              course VARCHAR(120) NOT NULL,
              cgpa NUMERIC(3, 2) NOT NULL,
              faculty_id INTEGER
            )
            """,
        ]
    return [
        """
        CREATE TABLE IF NOT EXISTS Department (
          department_id INT PRIMARY KEY,
          department_name VARCHAR(100) NOT NULL,
          location VARCHAR(100) NOT NULL
        )
        """,
        """
        CREATE TABLE IF NOT EXISTS Employee (
          employee_id INT PRIMARY KEY,
          name VARCHAR(120) NOT NULL,
          email VARCHAR(160) UNIQUE NOT NULL,
          department VARCHAR(100) NOT NULL,
          salary DECIMAL(12, 2) NOT NULL,
          joining_date DATE NOT NULL
        )
        """,
        """
        CREATE TABLE IF NOT EXISTS Students (
          student_id INT PRIMARY KEY,
          name VARCHAR(120) NOT NULL,
          email VARCHAR(160) UNIQUE NOT NULL,
          course VARCHAR(120) NOT NULL,
          cgpa DECIMAL(3, 2) NOT NULL,
          faculty_id INT
        )
        """,
    ]


def insert_statement(target: str, table: str, columns: tuple[str, ...]) -> str:
    column_sql = ", ".join(columns)
    params = ", ".join(f":{column}" for column in columns)
    if target == "postgres":
        key = columns[0]
        return f"INSERT INTO {table} ({column_sql}) VALUES ({params}) ON CONFLICT ({key}) DO NOTHING"
    return f"INSERT IGNORE INTO {table} ({column_sql}) VALUES ({params})"


def seed_target(target: str, url: str) -> None:
    engine = create_engine(url, pool_pre_ping=True)
    try:
        with engine.begin() as connection:
            for statement in statements_for(target):
                connection.execute(text(statement))
            department_insert = text(insert_statement(target, "Department", ("department_id", "department_name", "location")))
            employee_insert = text(
                insert_statement(target, "Employee", ("employee_id", "name", "email", "department", "salary", "joining_date"))
            )
            student_insert = text(
                insert_statement(target, "Students", ("student_id", "name", "email", "course", "cgpa", "faculty_id"))
            )
            connection.execute(department_insert, [dict(zip(("department_id", "department_name", "location"), row)) for row in DEPARTMENTS])
            connection.execute(employee_insert, [dict(zip(("employee_id", "name", "email", "department", "salary", "joining_date"), row)) for row in EMPLOYEES])
            connection.execute(student_insert, [dict(zip(("student_id", "name", "email", "course", "cgpa", "faculty_id"), row)) for row in STUDENTS])
    finally:
        engine.dispose()
    print(f"Initialized {target} demo schema and sample data.")


def main() -> None:
    load_environment(PROJECT_ROOT, SQL_SERVICE_ROOT)
    parser = argparse.ArgumentParser(description="Initialize managed cloud demo databases.")
    parser.add_argument("--target", choices=["postgres", "mysql", "all"], default="all")
    args = parser.parse_args()

    targets = ["postgres", "mysql"] if args.target == "all" else [args.target]
    env_names = {"postgres": "POSTGRES_DEMO_URL", "mysql": "MYSQL_DEMO_URL"}
    for target in targets:
        url = os.getenv(env_names[target])
        if not url:
            raise RuntimeError(f"{env_names[target]} is required to initialize {target}.")
        seed_target(target, url)


if __name__ == "__main__":
    main()
