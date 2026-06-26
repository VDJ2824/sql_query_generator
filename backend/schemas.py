"""Pydantic schemas for request and response payloads."""

from pydantic import BaseModel


class UserCreate(BaseModel):
    username: str
    password: str
    role: str
    department: str | None = None
    employee_id: int | None = None
    student_id: int | None = None


class UserLogin(BaseModel):
    username: str
    password: str


class Token(BaseModel):
    access_token: str
    token_type: str = "bearer"
    role: str
    username: str


class TokenData(BaseModel):
    username: str | None = None


class UserPublic(BaseModel):
    user_id: int
    username: str
    role: str
    department: str | None = None
    employee_id: int | None = None
    student_id: int | None = None

    model_config = {"from_attributes": True}


class SQLGenerationRequest(BaseModel):
    prompt: str


class SQLQueryOption(BaseModel):
    option_id: int
    title: str
    sql: str
    query_type: str
    tables_used: list[str]
    columns_used: list[str]
    explanation: str
    risk_level: str
    execution_allowed: bool
    requires_confirmation: bool
    warnings: list[str]


class SQLGenerationResponse(BaseModel):
    user_prompt: str
    query_options: list[SQLQueryOption]


class PreviewSelectedQueryRequest(BaseModel):
    selected_option_id: int


class PreviewSelectedQueryResponse(BaseModel):
    selected_option_id: int
    generated_sql: str
    final_enforced_sql: str
    preview_sql: str
    query_type: str
    estimated_rows: int
    preview_rows: list[dict]
    impact_message: str
    risk_level: str
    execution_allowed: bool
    requires_confirmation: bool
    warnings: list[str]


class ExecuteSelectedQueryRequest(BaseModel):
    selected_option_id: int
    confirmed: bool = False


class ExecuteSelectedQueryResponse(BaseModel):
    success: bool
    message: str
    generated_sql: str
    final_enforced_sql: str
    query_type: str
    rows_affected: int
    result_rows: list[dict]
    execution_allowed: bool


class SelectQueryRequest(BaseModel):
    option_id: int
    title: str
    sql: str
    query_type: str


class SelectedQueryResponse(BaseModel):
    selected_query_id: int
    user_id: int
    option_id: int
    title: str
    generated_sql: str
    query_type: str
    created_at: str
    expires_at: str
