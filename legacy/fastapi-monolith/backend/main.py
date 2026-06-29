"""FastAPI entrypoint for the secure AI SQL query generator."""

from fastapi import FastAPI, Depends
from fastapi import HTTPException, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from sqlalchemy import text
from sqlalchemy.orm import Session

from .audit_logger import get_audit_logs, get_user_history, log_audit_event
from .auth import (
    create_access_token,
    get_access_token_expire_minutes,
    hash_password,
    verify_password,
)
from .database import engine, initialize_database, get_db
from .dependencies import require_admin, require_authenticated_user
from .impact_analyzer import preview_selected_query
from .models import QueryHistory, User
from .query_executor import execute_selected_query
from .schema_reader import read_accessible_schema
from .selected_query import get_active_selected_query, select_query_option, selected_query_to_dict
from .schemas import (
    ExecuteSelectedQueryRequest,
    ExecuteSelectedQueryResponse,
    PreviewSelectedQueryRequest,
    PreviewSelectedQueryResponse,
    SQLGenerationRequest,
    SQLGenerationResponse,
    SelectQueryRequest,
    SelectedQueryResponse,
    Token,
    UserCreate,
    UserLogin,
    UserPublic,
)
from .sql_generator import generate_sql_options


app = FastAPI(
    title="Secure AI SQL Query Generator",
    description="Beginner-friendly starter backend for generating and validating SQL safely.",
    version="0.1.0",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=False,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.on_event("startup")
def create_database_tables() -> None:
    """Create starter tables and seed them when needed."""
    initialize_database()


@app.get("/")
def root() -> dict[str, str]:
    return {"message": "Secure AI SQL Query Generator backend is running."}


@app.get("/health")
def health(db: Session = Depends(get_db)) -> JSONResponse:
    try:
        db.execute(text("SELECT 1"))
        return JSONResponse(
            status_code=200,
            content={
                "status": "ok",
                "backend": "working",
                "database": "working",
            },
        )
    except Exception:
        return JSONResponse(
            status_code=503,
            content={
                "status": "error",
                "backend": "working",
                "database": "unavailable",
            },
        )


@app.post("/register", response_model=UserPublic, status_code=status.HTTP_201_CREATED)
def register(user_data: UserCreate, db: Session = Depends(get_db)) -> User:
    """Create a test user with a bcrypt-hashed password."""
    existing_user = db.query(User).filter(User.username == user_data.username).first()
    if existing_user:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Username already exists",
        )

    user = User(
        username=user_data.username,
        password_hash=hash_password(user_data.password),
        role=user_data.role,
        department=user_data.department,
        employee_id=user_data.employee_id,
        student_id=user_data.student_id,
    )
    db.add(user)
    db.commit()
    db.refresh(user)
    return user


@app.post("/login", response_model=Token)
def login(credentials: UserLogin, db: Session = Depends(get_db)) -> Token:
    """Validate credentials and return a JWT access token."""
    user = db.query(User).filter(User.username == credentials.username).first()
    if user is None or not verify_password(credentials.password, user.password_hash):
        log_audit_event(
            db,
            user_id=user.user_id if user else 0,
            action_type="login_failure",
            execution_status="failed",
            user_prompt=f"Login failed for username: {credentials.username}",
        )
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid username or password",
        )

    access_token = create_access_token(
        data={"sub": user.username, "role": user.role},
        expires_minutes=get_access_token_expire_minutes(),
    )
    log_audit_event(
        db,
        user_id=user.user_id,
        action_type="login_success",
        execution_status="success",
        user_prompt=f"Login succeeded for username: {user.username}",
    )
    return Token(
        access_token=access_token,
        token_type="bearer",
        role=user.role,
        username=user.username,
    )


@app.get("/me", response_model=UserPublic)
def read_me(current_user: User = Depends(require_authenticated_user)) -> User:
    return current_user


@app.get("/schema")
def get_schema(
    current_user: User = Depends(require_authenticated_user),
    db: Session = Depends(get_db),
) -> dict:
    log_audit_event(
        db,
        user_id=current_user.user_id,
        action_type="schema_access",
        execution_status="success",
    )
    return read_accessible_schema(engine, current_user)


@app.post("/generate", response_model=SQLGenerationResponse)
def generate_sql(
    request: SQLGenerationRequest,
    current_user: User = Depends(require_authenticated_user),
    db: Session = Depends(get_db),
) -> dict:
    accessible_schema = read_accessible_schema(engine, current_user)
    generated = generate_sql_options(request.prompt, current_user, accessible_schema)
    _save_generated_options(db, current_user, generated)
    log_audit_event(
        db,
        user_id=current_user.user_id,
        action_type="query_generation",
        user_prompt=request.prompt,
        query_type="GENERATE",
        execution_status="generated",
        rows_affected=len(generated.get("query_options", [])),
    )
    return generated


@app.post("/preview-selected-query", response_model=PreviewSelectedQueryResponse)
def preview_query(
    request: PreviewSelectedQueryRequest,
    current_user: User = Depends(require_authenticated_user),
    db: Session = Depends(get_db),
) -> dict:
    return preview_selected_query(
        db=db,
        current_user=current_user,
        selected_option_id=request.selected_option_id,
    )


@app.post("/execute-selected-query", response_model=ExecuteSelectedQueryResponse)
def execute_query(
    request: ExecuteSelectedQueryRequest,
    current_user: User = Depends(require_authenticated_user),
    db: Session = Depends(get_db),
) -> dict:
    return execute_selected_query(
        db=db,
        current_user=current_user,
        selected_option_id=request.selected_option_id,
        confirmed=request.confirmed,
    )


@app.post("/select-query", response_model=SelectedQueryResponse)
def select_query(
    request: SelectQueryRequest,
    current_user: User = Depends(require_authenticated_user),
    db: Session = Depends(get_db),
) -> dict:
    selected_query = select_query_option(
        db=db,
        current_user=current_user,
        option_id=request.option_id,
        title=request.title,
    )
    return selected_query_to_dict(selected_query)


@app.get("/selected-query", response_model=SelectedQueryResponse)
def read_selected_query(
    current_user: User = Depends(require_authenticated_user),
    db: Session = Depends(get_db),
) -> dict:
    selected_query = get_active_selected_query(db=db, current_user=current_user)
    if selected_query is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="No active selected query was found for this user.",
        )
    return selected_query_to_dict(selected_query)


@app.get("/history")
def history(
    current_user: User = Depends(require_authenticated_user),
    db: Session = Depends(get_db),
) -> list[dict]:
    return get_user_history(db, current_user.user_id)


@app.get("/admin/audit-logs")
def admin_audit_logs(
    user_id: int | None = None,
    query_type: str | None = None,
    execution_status: str | None = None,
    date_from: str | None = None,
    date_to: str | None = None,
    current_user: User = Depends(require_admin),
    db: Session = Depends(get_db),
) -> list[dict]:
    return get_audit_logs(
        db,
        user_id=user_id,
        query_type=query_type,
        execution_status=execution_status,
        date_from=date_from,
        date_to=date_to,
    )


def _save_generated_options(db: Session, current_user: User, generated: dict) -> None:
    for option in generated.get("query_options", []):
        db.add(
            QueryHistory(
                user_id=current_user.user_id,
                user_prompt=generated.get("user_prompt", ""),
                selected_option_id=option.get("option_id"),
                generated_sql=option.get("sql", ""),
                final_enforced_sql="",
                query_type=option.get("query_type", "UNKNOWN"),
                execution_status="generated",
                rows_affected=None,
            )
        )
    db.commit()
