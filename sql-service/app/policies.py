"""Policy helpers based on verified context received from Express."""

from __future__ import annotations

from .schemas import AccessPolicy, VerifiedUser


def active_policies_for_user(policies: list[AccessPolicy], user: VerifiedUser) -> list[AccessPolicy]:
    role = user.role.upper()
    return [policy for policy in policies if policy.active and policy.role.upper() == role]


def allowed_tables(policies: list[AccessPolicy], user: VerifiedUser) -> set[str]:
    tables: set[str] = set()
    for policy in active_policies_for_user(policies, user):
        tables.update(table.lower() for table in policy.allowedTables)
    return tables


def all_workspace_tables_allowed(policies: list[AccessPolicy], user: VerifiedUser) -> bool:
    return any(not policy.allowedTables for policy in active_policies_for_user(policies, user))


def blocked_tables(policies: list[AccessPolicy], user: VerifiedUser) -> set[str]:
    tables: set[str] = set()
    for policy in active_policies_for_user(policies, user):
        tables.update(table.lower() for table in policy.blockedTables)
    return tables


def allowed_operations_for_table(policies: list[AccessPolicy], user: VerifiedUser, table_name: str) -> set[str]:
    table = table_name.lower()
    operations: set[str] = set()
    for policy in active_policies_for_user(policies, user):
        policy_tables = {value.lower() for value in policy.allowedTables}
        if not policy_tables or table in policy_tables:
            operations.update(operation.upper() for operation in policy.allowedOperations)
    return operations


def allowed_columns_for_table(policies: list[AccessPolicy], user: VerifiedUser, table_name: str) -> set[str]:
    table = table_name.lower()
    columns: set[str] = set()
    for policy in active_policies_for_user(policies, user):
        policy_tables = {value.lower() for value in policy.allowedTables}
        if not policy_tables or table in policy_tables:
            columns.update(column.lower() for column in policy.allowedColumns)
    return columns


def requires_confirmation_for_query(policies: list[AccessPolicy], user: VerifiedUser, query_type: str) -> bool:
    normalized_query_type = query_type.upper()
    for policy in active_policies_for_user(policies, user):
        if normalized_query_type in {value.upper() for value in policy.requiresConfirmationFor}:
            return True
    return normalized_query_type in {"INSERT", "UPDATE", "DELETE"}
