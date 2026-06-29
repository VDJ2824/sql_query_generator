"""Row-level authorization enforcement for target SQL statements."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

import sqlglot
from sqlglot import exp

from .policies import active_policies_for_user
from .schemas import AccessPolicy, VerifiedUser


SUPPORTED_QUERY_TYPES = {"SELECT", "UPDATE", "DELETE", "INSERT"}


@dataclass
class RowLevelSecurityResult:
    generatedSql: str
    finalEnforcedSql: str
    securityFilterExplanation: str
    parameters: dict[str, Any] = field(default_factory=dict)
    isEnforced: bool = True
    securityErrors: list[str] = field(default_factory=list)


class RowLevelSecurityService:
    """Normalize SQL after policy checks.

    The general-purpose version does not use employee/student identity filters.
    Access is controlled by connection, schema, table, column, and operation.
    """

    def __init__(self, user: VerifiedUser, policies: list[AccessPolicy], dialect: str):
        self.user = user
        self.policies = policies
        self.dialect = dialect

    def enforce(self, sql: str) -> RowLevelSecurityResult:
        generated_sql = sql.strip().rstrip(";")
        query_type = self._classify_query(generated_sql)
        if query_type == "DDL":
            return RowLevelSecurityResult(
                generatedSql=generated_sql,
                finalEnforcedSql=generated_sql,
                securityFilterExplanation="DDL is limited by access policy and dangerous database-administration commands are blocked.",
                isEnforced=True,
            )
        if query_type not in SUPPORTED_QUERY_TYPES:
            return RowLevelSecurityResult(
                generatedSql=generated_sql,
                finalEnforcedSql=generated_sql,
                securityFilterExplanation=f"Row-level enforcement is not applicable to {query_type}.",
                isEnforced=query_type not in {"UNKNOWN", "DDL", "DCL"},
            )

        try:
            expression = sqlglot.parse_one(generated_sql, dialect=self.dialect)
        except sqlglot.errors.ParseError as exc:
            return self._rejected(generated_sql, f"Row-level enforcement failed because SQL could not be parsed: {exc}")

        structure_error = self._unsupported_structure_error(expression)
        if structure_error:
            return self._rejected(generated_sql, structure_error)

        table_name = self._single_table_name(expression)
        if not table_name:
            return self._rejected(generated_sql, "Row-level enforcement requires exactly one target table.")

        return RowLevelSecurityResult(
            generatedSql=generated_sql,
            finalEnforcedSql=expression.sql(dialect=self.dialect).rstrip(";"),
            securityFilterExplanation="No identity-based row-level restriction is configured for this general SQL policy.",
            parameters={},
            isEnforced=True,
        )

    def _single_table_name(self, expression: exp.Expression) -> str:
        table_names = {table.name.lower() for table in expression.find_all(exp.Table) if table.name}
        if len(table_names) != 1:
            return ""
        return next(iter(table_names))

    def _unsupported_structure_error(self, expression: exp.Expression) -> str:
        if list(expression.find_all(exp.Join)):
            return "Row-level enforcement rejected JOIN because filters cannot be guaranteed."
        if list(expression.find_all(exp.Union)):
            return "Row-level enforcement rejected UNION because filters cannot be guaranteed."
        if list(expression.find_all(exp.With)):
            return "Row-level enforcement rejected CTE because filters cannot be guaranteed."
        if list(expression.find_all(exp.Subquery)):
            return "Row-level enforcement rejected nested query because filters cannot be guaranteed."
        if len(list(expression.find_all(exp.Select))) > 1:
            return "Row-level enforcement rejected nested SELECT because filters cannot be guaranteed."
        return ""

    def _rejected(self, generated_sql: str, error: str) -> RowLevelSecurityResult:
        return RowLevelSecurityResult(
            generatedSql=generated_sql,
            finalEnforcedSql="",
            securityFilterExplanation=error,
            parameters={},
            isEnforced=False,
            securityErrors=[error],
        )

    def _classify_query(self, sql: str) -> str:
        first_word = sql.strip().split(" ", 1)[0].upper() if sql.strip() else ""
        if first_word in {"CREATE", "ALTER", "DROP", "TRUNCATE"}:
            return "DDL"
        if first_word in SUPPORTED_QUERY_TYPES:
            return first_word
        return "OTHER"
