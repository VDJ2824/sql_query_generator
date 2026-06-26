"""Database setup and initialization helpers."""

from __future__ import annotations

from datetime import date
from pathlib import Path

from passlib.context import CryptContext
from sqlalchemy import create_engine, func, inspect, select
from sqlalchemy.orm import Session, declarative_base, sessionmaker


BASE_DIR = Path(__file__).resolve().parent.parent
DATABASE_PATH = BASE_DIR / "database" / "company.db"
DATABASE_URL = f"sqlite:///{DATABASE_PATH}"

engine = create_engine(
    DATABASE_URL,
    connect_args={"check_same_thread": False},
)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
Base = declarative_base()

pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")


def get_db():
    """Yield a SQLAlchemy session for FastAPI dependencies."""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def _hash_password(password: str) -> str:
    return pwd_context.hash(password)


def _database_has_data(db: Session) -> bool:
    from .models import AuditLogs, Employee, QueryHistory, Student, User

    tables = [User, Employee, Student, QueryHistory, AuditLogs]
    for table in tables:
        if db.scalar(select(func.count()).select_from(table)) > 0:
            return True
    return False


def _seed_employees() -> list[dict]:
    """Return 25 realistic employee rows."""
    return [
        {
            "employee_id": 1,
            "name": "Aarav Mehta",
            "email": "aarav.mehta@example.com",
            "department": "IT",
            "salary": 92000.0,
            "joining_date": date(2020, 4, 12),
            "manager_id": None,
        },
        {
            "employee_id": 2,
            "name": "Neha Sharma",
            "email": "neha.sharma@example.com",
            "department": "HR",
            "salary": 88000.0,
            "joining_date": date(2019, 8, 5),
            "manager_id": None,
        },
        {
            "employee_id": 3,
            "name": "Rohan Kapoor",
            "email": "rohan.kapoor@example.com",
            "department": "Finance",
            "salary": 86000.0,
            "joining_date": date(2021, 2, 18),
            "manager_id": None,
        },
        {
            "employee_id": 4,
            "name": "Priya Nair",
            "email": "priya.nair@example.com",
            "department": "Sales",
            "salary": 84000.0,
            "joining_date": date(2020, 11, 2),
            "manager_id": None,
        },
        {
            "employee_id": 5,
            "name": "Kabir Singh",
            "email": "kabir.singh@example.com",
            "department": "Operations",
            "salary": 81000.0,
            "joining_date": date(2018, 6, 21),
            "manager_id": None,
        },
        {
            "employee_id": 6,
            "name": "Isha Verma",
            "email": "isha.verma@example.com",
            "department": "IT",
            "salary": 72000.0,
            "joining_date": date(2022, 1, 10),
            "manager_id": 1,
        },
        {
            "employee_id": 7,
            "name": "Arjun Patel",
            "email": "arjun.patel@example.com",
            "department": "IT",
            "salary": 76000.0,
            "joining_date": date(2021, 7, 14),
            "manager_id": 1,
        },
        {
            "employee_id": 8,
            "name": "Simran Kaur",
            "email": "simran.kaur@example.com",
            "department": "IT",
            "salary": 69000.0,
            "joining_date": date(2023, 3, 4),
            "manager_id": 1,
        },
        {
            "employee_id": 9,
            "name": "Vikram Joshi",
            "email": "vikram.joshi@example.com",
            "department": "HR",
            "salary": 67000.0,
            "joining_date": date(2022, 9, 19),
            "manager_id": 2,
        },
        {
            "employee_id": 10,
            "name": "Ananya Rao",
            "email": "ananya.rao@example.com",
            "department": "HR",
            "salary": 64000.0,
            "joining_date": date(2023, 5, 11),
            "manager_id": 2,
        },
        {
            "employee_id": 11,
            "name": "Farhan Ali",
            "email": "farhan.ali@example.com",
            "department": "Finance",
            "salary": 73000.0,
            "joining_date": date(2020, 2, 7),
            "manager_id": 3,
        },
        {
            "employee_id": 12,
            "name": "Meera Iyer",
            "email": "meera.iyer@example.com",
            "department": "Finance",
            "salary": 70000.0,
            "joining_date": date(2021, 10, 25),
            "manager_id": 3,
        },
        {
            "employee_id": 13,
            "name": "Sahil Khan",
            "email": "sahil.khan@example.com",
            "department": "Sales",
            "salary": 71000.0,
            "joining_date": date(2022, 4, 8),
            "manager_id": 4,
        },
        {
            "employee_id": 14,
            "name": "Tanya Desai",
            "email": "tanya.desai@example.com",
            "department": "Sales",
            "salary": 66000.0,
            "joining_date": date(2023, 1, 16),
            "manager_id": 4,
        },
        {
            "employee_id": 15,
            "name": "Nikhil Bansal",
            "email": "nikhil.bansal@example.com",
            "department": "Operations",
            "salary": 68000.0,
            "joining_date": date(2020, 12, 1),
            "manager_id": 5,
        },
        {
            "employee_id": 16,
            "name": "Pooja Kulkarni",
            "email": "pooja.kulkarni@example.com",
            "department": "Operations",
            "salary": 65000.0,
            "joining_date": date(2021, 6, 30),
            "manager_id": 5,
        },
        {
            "employee_id": 17,
            "name": "Dev Malhotra",
            "email": "dev.malhotra@example.com",
            "department": "IT",
            "salary": 78000.0,
            "joining_date": date(2022, 8, 22),
            "manager_id": 1,
        },
        {
            "employee_id": 18,
            "name": "Ritika Gupta",
            "email": "ritika.gupta@example.com",
            "department": "HR",
            "salary": 62000.0,
            "joining_date": date(2023, 2, 13),
            "manager_id": 2,
        },
        {
            "employee_id": 19,
            "name": "Aditya Sen",
            "email": "aditya.sen@example.com",
            "department": "Finance",
            "salary": 76000.0,
            "joining_date": date(2019, 9, 9),
            "manager_id": 3,
        },
        {
            "employee_id": 20,
            "name": "Kavya Menon",
            "email": "kavya.menon@example.com",
            "department": "Sales",
            "salary": 69000.0,
            "joining_date": date(2022, 11, 28),
            "manager_id": 4,
        },
        {
            "employee_id": 21,
            "name": "Rahul Yadav",
            "email": "rahul.yadav@example.com",
            "department": "Operations",
            "salary": 64000.0,
            "joining_date": date(2021, 4, 18),
            "manager_id": 5,
        },
        {
            "employee_id": 22,
            "name": "Sana Sheikh",
            "email": "sana.sheikh@example.com",
            "department": "IT",
            "salary": 80000.0,
            "joining_date": date(2020, 5, 6),
            "manager_id": 1,
        },
        {
            "employee_id": 23,
            "name": "Owen Thomas",
            "email": "owen.thomas@example.com",
            "department": "HR",
            "salary": 63000.0,
            "joining_date": date(2022, 7, 20),
            "manager_id": 2,
        },
        {
            "employee_id": 24,
            "name": "Maya Fernandez",
            "email": "maya.fernandez@example.com",
            "department": "Finance",
            "salary": 74000.0,
            "joining_date": date(2021, 12, 14),
            "manager_id": 3,
        },
        {
            "employee_id": 25,
            "name": "Zoya Ahmed",
            "email": "zoya.ahmed@example.com",
            "department": "Sales",
            "salary": 65000.0,
            "joining_date": date(2023, 4, 27),
            "manager_id": 4,
        },
    ]


def _seed_students() -> list[dict]:
    """Return 25 realistic student rows."""
    return [
        {"student_id": 1, "name": "Aditi Rao", "email": "aditi.rao@student.example.com", "course": "Computer Science", "cgpa": 9.4, "faculty_id": 1},
        {"student_id": 2, "name": "Yash Jain", "email": "yash.jain@student.example.com", "course": "Data Science", "cgpa": 8.9, "faculty_id": 1},
        {"student_id": 3, "name": "Naina Kapoor", "email": "naina.kapoor@student.example.com", "course": "Information Systems", "cgpa": 8.2, "faculty_id": 1},
        {"student_id": 4, "name": "Karan Mehta", "email": "karan.mehta@student.example.com", "course": "Electronics", "cgpa": 7.8, "faculty_id": 2},
        {"student_id": 5, "name": "Ira Shah", "email": "ira.shah@student.example.com", "course": "Mechanical Engineering", "cgpa": 8.1, "faculty_id": 2},
        {"student_id": 6, "name": "Devika Nair", "email": "devika.nair@student.example.com", "course": "Computer Science", "cgpa": 9.1, "faculty_id": 1},
        {"student_id": 7, "name": "Rahul Bose", "email": "rahul.bose@student.example.com", "course": "Business Administration", "cgpa": 7.4, "faculty_id": 2},
        {"student_id": 8, "name": "Sana Khan", "email": "sana.khan@student.example.com", "course": "Data Science", "cgpa": 8.7, "faculty_id": 1},
        {"student_id": 9, "name": "Om Verma", "email": "om.verma@student.example.com", "course": "Cyber Security", "cgpa": 9.0, "faculty_id": 1},
        {"student_id": 10, "name": "Pallavi Singh", "email": "pallavi.singh@student.example.com", "course": "MBA", "cgpa": 7.9, "faculty_id": 2},
        {"student_id": 11, "name": "Arjun Roy", "email": "arjun.roy@student.example.com", "course": "Computer Science", "cgpa": 8.6, "faculty_id": 1},
        {"student_id": 12, "name": "Megha Iyer", "email": "megha.iyer@student.example.com", "course": "Physics", "cgpa": 8.3, "faculty_id": 2},
        {"student_id": 13, "name": "Rohit Das", "email": "rohit.das@student.example.com", "course": "Mathematics", "cgpa": 7.7, "faculty_id": 2},
        {"student_id": 14, "name": "Simran Gill", "email": "simran.gill@student.example.com", "course": "Data Science", "cgpa": 9.2, "faculty_id": 1},
        {"student_id": 15, "name": "Aman Patel", "email": "aman.patel@student.example.com", "course": "Information Systems", "cgpa": 8.0, "faculty_id": 1},
        {"student_id": 16, "name": "Zara Sheikh", "email": "zara.sheikh@student.example.com", "course": "Electronics", "cgpa": 8.8, "faculty_id": 2},
        {"student_id": 17, "name": "Kabir Arora", "email": "kabir.arora@student.example.com", "course": "Computer Science", "cgpa": 9.5, "faculty_id": 1},
        {"student_id": 18, "name": "Anika Joshi", "email": "anika.joshi@student.example.com", "course": "Chemistry", "cgpa": 7.6, "faculty_id": 2},
        {"student_id": 19, "name": "Mihir Sethi", "email": "mihir.sethi@student.example.com", "course": "Business Administration", "cgpa": 8.4, "faculty_id": 2},
        {"student_id": 20, "name": "Prachi Malhotra", "email": "prachi.malhotra@student.example.com", "course": "Cyber Security", "cgpa": 9.3, "faculty_id": 1},
        {"student_id": 21, "name": "Riya Nanda", "email": "riya.nanda@student.example.com", "course": "Mathematics", "cgpa": 8.5, "faculty_id": 2},
        {"student_id": 22, "name": "Harsh Jain", "email": "harsh.jain@student.example.com", "course": "Physics", "cgpa": 7.9, "faculty_id": 2},
        {"student_id": 23, "name": "Tanya Kapoor", "email": "tanya.kapoor@student.example.com", "course": "Computer Science", "cgpa": 9.0, "faculty_id": 1},
        {"student_id": 24, "name": "Neel Bhatia", "email": "neel.bhatia@student.example.com", "course": "MBA", "cgpa": 8.1, "faculty_id": 2},
        {"student_id": 25, "name": "Ishita Rao", "email": "ishita.rao@student.example.com", "course": "Information Systems", "cgpa": 8.7, "faculty_id": 1},
    ]


def _seed_users() -> list[dict]:
    """Return users for admin, faculty, managers, employees, and students."""
    return [
        {
            "user_id": 1,
            "username": "admin",
            "password_hash": _hash_password("admin123"),
            "role": "admin",
            "department": "Administration",
            "employee_id": None,
            "student_id": None,
        },
        {
            "user_id": 2,
            "username": "faculty_it",
            "password_hash": _hash_password("faculty123"),
            "role": "faculty",
            "department": "IT",
            "employee_id": None,
            "student_id": None,
        },
        {
            "user_id": 3,
            "username": "faculty_business",
            "password_hash": _hash_password("faculty123"),
            "role": "faculty",
            "department": "Business",
            "employee_id": None,
            "student_id": None,
        },
        {
            "user_id": 4,
            "username": "it_manager",
            "password_hash": _hash_password("manager123"),
            "role": "manager",
            "department": "IT",
            "employee_id": 1,
            "student_id": None,
        },
        {
            "user_id": 5,
            "username": "hr_manager",
            "password_hash": _hash_password("manager123"),
            "role": "manager",
            "department": "HR",
            "employee_id": 2,
            "student_id": None,
        },
        {
            "user_id": 6,
            "username": "employee_6",
            "password_hash": _hash_password("employee123"),
            "role": "employee",
            "department": "IT",
            "employee_id": 6,
            "student_id": None,
        },
        {
            "user_id": 7,
            "username": "employee_7",
            "password_hash": _hash_password("employee123"),
            "role": "employee",
            "department": "Finance",
            "employee_id": 11,
            "student_id": None,
        },
        {
            "user_id": 8,
            "username": "employee_8",
            "password_hash": _hash_password("employee123"),
            "role": "employee",
            "department": "Sales",
            "employee_id": 13,
            "student_id": None,
        },
        {
            "user_id": 9,
            "username": "student_1",
            "password_hash": _hash_password("student123"),
            "role": "student",
            "department": None,
            "employee_id": None,
            "student_id": 1,
        },
        {
            "user_id": 10,
            "username": "student_2",
            "password_hash": _hash_password("student123"),
            "role": "student",
            "department": None,
            "employee_id": None,
            "student_id": 2,
        },
        {
            "user_id": 11,
            "username": "student_3",
            "password_hash": _hash_password("student123"),
            "role": "student",
            "department": None,
            "employee_id": None,
            "student_id": 3,
        },
    ]


def initialize_database() -> None:
    """Create tables and seed sample data if the database is empty."""
    from .models import AuditLogs, Employee, QueryHistory, Student, User

    Base.metadata.create_all(bind=engine)
    with SessionLocal() as db:
        if _database_has_data(db):
            return

        db.add_all(Employee(**row) for row in _seed_employees())
        db.add_all(Student(**row) for row in _seed_students())
        db.flush()

        db.add_all(User(**row) for row in _seed_users())
        db.flush()

        db.add_all(
            [
                QueryHistory(
                    user_id=1,
                    user_prompt="Show all employees in the IT department.",
                    selected_option_id=1,
                    generated_sql="SELECT * FROM employees WHERE department = 'IT';",
                    final_enforced_sql="SELECT * FROM employees WHERE department = 'IT';",
                    query_type="SELECT",
                    execution_status="seeded",
                    rows_affected=5,
                ),
                AuditLogs(
                    user_id=1,
                    action_type="seed_initial_data",
                    user_prompt=None,
                    generated_sql=None,
                    final_enforced_sql=None,
                    query_type=None,
                    execution_status="seeded",
                    rows_affected=None,
                ),
            ]
        )
        db.commit()
