"""Pydantic request and response models for internal service contracts."""

from __future__ import annotations

from typing import Any

from pydantic import BaseModel, Field


class VerifiedUser(BaseModel):
    userId: str
    role: str
    workspaceIdentifier: str | None = None
    postgresWorkspaceName: str | None = None
    tidbWorkspaceName: str | None = None


class DatabaseConnectionContext(BaseModel):
    connectionId: str
    databaseType: str
    dialect: str | None = None
    credentialEnvironmentVariableName: str


class AccessPolicy(BaseModel):
    role: str
    databaseConnectionId: str | None = None
    allowedOperations: list[str] = Field(default_factory=list)
    allowedSchemas: list[str] = Field(default_factory=list)
    allowedTables: list[str] = Field(default_factory=list)
    blockedTables: list[str] = Field(default_factory=list)
    allowedColumns: list[str] = Field(default_factory=list)
    requiresPreviewFor: list[str] = Field(default_factory=lambda: ["INSERT", "UPDATE", "DELETE"])
    requiresConfirmationFor: list[str] = Field(default_factory=lambda: ["INSERT", "UPDATE", "DELETE"])
    active: bool = True


class InternalRequest(BaseModel):
    verifiedUser: VerifiedUser
    databaseConnection: DatabaseConnectionContext
    accessPolicies: list[AccessPolicy] = Field(default_factory=list)
    prompt: str = ""
    generatedSql: str | None = None
    selectedOptionId: int | None = None
    confirmed: bool = False
    typedConfirmation: str | None = None


class ValidationResult(BaseModel):
    isValid: bool
    queryType: str
    queryCategory: str = ""
    executionAllowed: bool
    requiresConfirmation: bool
    normalizedSql: str = ""
    warnings: list[str] = Field(default_factory=list)
    securityErrors: list[str] = Field(default_factory=list)


class QueryOption(BaseModel):
    optionId: int
    title: str
    generatedSql: str
    finalEnforcedSql: str = ""
    securityFilterExplanation: str = ""
    databaseType: str
    sqlDialect: str
    queryType: str
    tablesUsed: list[str] = Field(default_factory=list)
    columnsUsed: list[str] = Field(default_factory=list)
    explanation: str = ""
    riskLevel: str = "low"
    executionAllowed: bool = False
    requiresConfirmation: bool = False
    warnings: list[str] = Field(default_factory=list)


class GenerateResponse(BaseModel):
    queryOptions: list[QueryOption]


class SchemaResponse(BaseModel):
    role: str
    dialect: str
    allowedTables: list[dict[str, Any]]


class PreviewResponse(BaseModel):
    generatedSql: str
    finalEnforcedSql: str
    securityFilterExplanation: str = ""
    previewSql: str
    queryType: str
    estimatedRows: int = 0
    previewRows: list[dict[str, Any]] = Field(default_factory=list)
    impactMessage: str
    riskLevel: str
    executionAllowed: bool
    requiresConfirmation: bool
    warnings: list[str] = Field(default_factory=list)
    securityErrors: list[str] = Field(default_factory=list)
    confirmationToken: str | None = None
    requiredTypedConfirmation: str | None = None
    ddlDetails: dict[str, Any] = Field(default_factory=dict)


class ExecuteResponse(BaseModel):
    success: bool
    message: str
    generatedSql: str
    finalEnforcedSql: str
    securityFilterExplanation: str = ""
    queryType: str
    rowsAffected: int = 0
    resultRows: list[dict[str, Any]] = Field(default_factory=list)
    executionAllowed: bool
