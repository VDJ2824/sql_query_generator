"""NLP and AI SQL generation service.

The AI is only a suggestion engine. Every generated option is validated,
deduplicated, and row-level enforced before it is returned to Express.
"""

from __future__ import annotations

import json
import re
from typing import Any

import sqlglot
from sqlalchemy.engine import Engine
from sqlglot import exp

from .config import gemini_api_key, gemini_model
from .policies import active_policies_for_user
from .row_level_security_service import RowLevelSecurityService
from .schema_reader import read_allowed_schema, schema_from_policies
from .schemas import GenerateResponse, InternalRequest, QueryOption
from .sql_security import classify_query, classify_sql_command, validate_sql


class SqlGenerationService:
    """Generate safe SQL alternatives from natural-language prompts."""

    def __init__(
        self,
        engine: Engine | None,
        request: InternalRequest,
        dialect: str,
        allowed_schema: dict[str, Any] | None = None,
        schema_warning: str = "",
    ):
        self.engine = engine
        self.request = request
        self.dialect = dialect
        self.database_type = request.databaseConnection.databaseType.upper()
        self.schema_warning = schema_warning
        if allowed_schema is not None:
            self.allowed_schema = allowed_schema
        elif engine is not None:
            self.allowed_schema = read_allowed_schema(
                engine,
                request.verifiedUser,
                request.accessPolicies,
                dialect,
            )
        else:
            self.allowed_schema = schema_from_policies(request.verifiedUser, request.accessPolicies, dialect)

    def generate(self) -> GenerateResponse:
        if self._is_database_admin_intent():
            return GenerateResponse(queryOptions=[self._blocked_database_admin_option()])

        if self._is_ddl_intent():
            options = self._build_safe_options(self._ddl_raw_options())
            if options:
                return GenerateResponse(queryOptions=options[:3])
            return GenerateResponse(queryOptions=[self._blocked_ddl_option()])

        missing_table_option = self._missing_table_option()
        if missing_table_option:
            return GenerateResponse(queryOptions=[missing_table_option])

        ai_payload = self._call_ai()
        raw_options = self._extract_raw_options(ai_payload)
        options = self._build_safe_options(raw_options)

        if not options:
            options = self._build_safe_options(self._fallback_raw_options())

        if not options:
            options = [self._missing_table_option() or self._clarification_option()]

        return GenerateResponse(queryOptions=options[:3])

    def _call_ai(self) -> dict[str, Any] | None:
        api_key = gemini_api_key()
        if not api_key:
            return None

        system_prompt = (
            "You are a SQL generation assistant inside a secure internal service. "
            "Return only structured JSON. Do not include markdown. Generate at most "
            "3 meaningfully different SQL alternatives. Never invent table names or "
            "column names. Never use restricted columns. Never bypass row-level rules. "
            "For INSERT statements, use the exact table schema. Include every column "
            "where requiredForInsert is true. Do not assume primary keys are auto-incrementing "
            "unless the schema explicitly shows a default or generated value."
        )
        user_prompt = {
            "databaseType": self.database_type,
            "sqlDialect": self.dialect,
            "allowedTables": self.allowed_schema.get("allowedTables", []),
            "rowLevelPolicies": self._row_policy_summary(),
            "naturalLanguageRequest": self.request.prompt,
            "responseShape": {
                "queryOptions": [
                    {
                        "optionId": 1,
                        "title": "",
                        "generatedSql": "",
                        "queryType": "",
                        "tablesUsed": [],
                        "columnsUsed": [],
                        "explanation": "",
                        "riskLevel": "",
                        "executionAllowed": True,
                        "requiresConfirmation": False,
                        "warnings": [],
                    }
                ]
            },
        }

        try:
            from google import genai
            from google.genai import types

            client = genai.Client(api_key=api_key)
            response = client.models.generate_content(
                model=gemini_model(),
                contents=json.dumps(user_prompt),
                config=types.GenerateContentConfig(
                    system_instruction=system_prompt,
                    temperature=0.2,
                    response_mime_type="application/json",
                ),
            )
            return json.loads(response.text or "{}")
        except Exception:
            return None

    def _extract_raw_options(self, payload: dict[str, Any] | None) -> list[dict[str, Any]]:
        if not payload:
            return []
        raw_options = payload.get("queryOptions") or payload.get("query_options") or []
        return raw_options if isinstance(raw_options, list) else []

    def _build_safe_options(self, raw_options: list[dict[str, Any]]) -> list[QueryOption]:
        options: list[QueryOption] = []
        seen_sql: set[str] = set()

        for raw_option in raw_options:
            sql = str(raw_option.get("generatedSql") or raw_option.get("sql") or "").strip()
            if not sql:
                continue

            validation = validate_sql(sql, self.request.verifiedUser, self.request.accessPolicies, self.dialect)
            if not validation.isValid:
                continue
            if classify_sql_command(sql) == "INSERT" and self._missing_required_insert_columns(sql):
                continue

            normalized_key = self._semantic_dedupe_key(validation.normalizedSql)
            if normalized_key in seen_sql:
                continue
            seen_sql.add(normalized_key)

            rls_result = RowLevelSecurityService(
                self.request.verifiedUser,
                self.request.accessPolicies,
                self.dialect,
            ).enforce(
                validation.normalizedSql,
            )
            if not rls_result.isEnforced:
                continue
            generated_sql = sql if validation.queryType == "DDL" else validation.normalizedSql
            options.append(
                QueryOption(
                    optionId=len(options) + 1,
                    title=str(raw_option.get("title") or self._title_for(validation.queryType)),
                    generatedSql=generated_sql,
                    finalEnforcedSql=rls_result.finalEnforcedSql,
                    securityFilterExplanation=rls_result.securityFilterExplanation,
                    databaseType=self.database_type,
                    sqlDialect=self.dialect,
                    queryType=validation.queryType,
                    tablesUsed=self._tables_used(generated_sql),
                    columnsUsed=self._columns_used(generated_sql),
                    explanation=str(raw_option.get("explanation") or "Validated SQL option generated for the request."),
                    riskLevel=self._risk_level(validation.queryType),
                    executionAllowed=validation.executionAllowed,
                    requiresConfirmation=validation.requiresConfirmation,
                    warnings=self._unique_strings(list(raw_option.get("warnings") or []) + validation.warnings),
                )
            )
            if self.schema_warning:
                options[-1].warnings = self._unique_strings(options[-1].warnings + [self.schema_warning])
            if len(options) == 3:
                break

        return options

    def _fallback_raw_options(self) -> list[dict[str, Any]]:
        if self._is_ddl_intent():
            return self._ddl_raw_options()

        table = self._best_table()
        if not table:
            return []

        table_name = table["tableName"]
        columns = [column["name"] for column in table.get("allowedColumns", [])]
        prompt = self.request.prompt.lower()
        options: list[dict[str, Any]] = []

        if "insert" in prompt or "add" in prompt:
            insert_option = self._insert_records_option(table)
            if insert_option:
                options.append(insert_option)

        if "count" in prompt or "how many" in prompt:
            options.append(
                {
                    "title": f"Count {table_name} records",
                    "generatedSql": f"SELECT COUNT(*) AS total_records FROM {table_name}",
                    "explanation": "Counts authorized records after row-level enforcement.",
                }
            )

        salary_value = self._extract_number_after(prompt, "salary")
        if salary_value is not None and self._has_column(columns, "salary"):
            selected = self._select_columns(columns, ["id", "name", "salary", "amount"])
            options.append(
                {
                    "title": f"Salary greater than {salary_value:g}",
                    "generatedSql": f"SELECT {selected} FROM {table_name} WHERE salary > {salary_value:g}",
                    "explanation": "Shows accessible rows above the requested salary value.",
                }
            )

        top_n = self._extract_top_n(prompt)
        if top_n is not None and self._has_column(columns, "cgpa"):
            selected = self._select_columns(columns, ["student_id", "name", "course", "cgpa"])
            options.append(
                {
                    "title": f"Top {top_n} rows by CGPA",
                    "generatedSql": f"SELECT {selected} FROM {table_name} ORDER BY cgpa DESC LIMIT {top_n}",
                    "explanation": "Ranks accessible rows by CGPA.",
                }
            )

        if "update" in prompt and "salary" in prompt and self._has_column(columns, "salary"):
            percent = self._extract_percentage(prompt) or 5
            options.append(
                {
                    "title": f"Increase salary by {percent:g} percent",
                    "generatedSql": f"UPDATE {table_name} SET salary = salary * {1 + (percent / 100):g} WHERE salary IS NOT NULL",
                    "explanation": "Requires preview and confirmation before execution.",
                }
            )

        if "delete" in prompt and columns:
            id_column = self._first_existing_column(columns, ["id", "employee_id", "student_id"])
            if id_column:
                options.append(
                    {
                        "title": "Delete by identifier template",
                        "generatedSql": f"DELETE FROM {table_name} WHERE {id_column} = -1",
                        "explanation": "Safe template with a non-matching identifier unless edited by the backend workflow.",
                    }
                )

        if not options:
            detailed = self._select_columns(columns, columns[:6])
            selected = self._select_columns(columns, columns[:3])
            options.extend(
                [
                    {
                        "title": f"Detailed {table_name} records",
                        "generatedSql": f"SELECT {detailed} FROM {table_name}",
                        "explanation": "Detailed rows using allowed columns only.",
                    },
                    {
                        "title": f"Basic {table_name} view",
                        "generatedSql": f"SELECT {selected} FROM {table_name}",
                        "explanation": "Smaller view with fewer columns.",
                    },
                    {
                        "title": f"Count {table_name} records",
                        "generatedSql": f"SELECT COUNT(*) AS total_records FROM {table_name}",
                        "explanation": "Aggregate count of accessible rows.",
                    },
                ]
            )

        return options[:5]

    def _clarification_option(self) -> QueryOption:
        return QueryOption(
            optionId=1,
            title="Clarification needed",
            generatedSql="",
            finalEnforcedSql="",
            databaseType=self.database_type,
            sqlDialect=self.dialect,
            queryType="UNKNOWN",
            explanation="The request could not be converted into a safe authorized SQL option. Express should ask the user to clarify.",
            riskLevel="low",
            executionAllowed=False,
            requiresConfirmation=False,
            warnings=["No safe SQL alternatives were available for this prompt."],
        )

    def _missing_table_option(self) -> QueryOption | None:
        table_name = self._table_name_from_prompt()
        if not table_name:
            return None
        prompt = self.request.prompt.lower()
        if not any(keyword in prompt for keyword in ("insert", "update", "delete", "select", "show", "count")):
            return None
        existing_tables = {table.get("tableName", "").lower() for table in self.allowed_schema.get("allowedTables", [])}
        if table_name.lower() in existing_tables:
            return None
        return QueryOption(
            optionId=1,
            title=f"{table_name} table is not available in this workspace",
            generatedSql="",
            finalEnforcedSql="",
            databaseType=self.database_type,
            sqlDialect=self.dialect,
            queryType="UNKNOWN",
            explanation=(
                f"The selected private {self.database_type} workspace does not currently expose a table named "
                f"{table_name}. Create the table in this same selected database first, then generate the INSERT again."
            ),
            riskLevel="low",
            executionAllowed=False,
            requiresConfirmation=False,
            warnings=[
                f"Table '{table_name}' was not found in your private workspace schema.",
                "Tables created before private workspace isolation may exist in the old shared database, not in this workspace.",
            ],
        )

    def _blocked_ddl_option(self) -> QueryOption:
        return QueryOption(
            optionId=1,
            title="DDL request cannot be safely generated",
            generatedSql="",
            finalEnforcedSql="",
            databaseType=self.database_type,
            sqlDialect=self.dialect,
            queryType="DDL",
            explanation=(
                "The prompt asks for a database structure change, but a safe allow-listed DDL statement "
                "could not be generated from the prompt and active policy."
            ),
            riskLevel="high",
            executionAllowed=False,
            requiresConfirmation=False,
            warnings=[
                "No SELECT query was generated because the prompt is asking to create or modify schema.",
                "Use simple identifiers such as: create table named Student with columns id, name, email.",
            ],
        )

    def _blocked_database_admin_option(self) -> QueryOption:
        return QueryOption(
            optionId=1,
            title="Database administration is restricted",
            generatedSql="",
            finalEnforcedSql="",
            databaseType=self.database_type,
            sqlDialect=self.dialect,
            queryType="DDL",
            explanation=(
                "The request asks for database-level administration. This application allows safe table-level "
                "DDL in the selected workspace, but database creation, users, roles, grants, and system changes "
                "are blocked."
            ),
            riskLevel="critical",
            executionAllowed=False,
            requiresConfirmation=False,
            warnings=["Database-level administration is restricted for security."],
        )

    def _ddl_raw_options(self) -> list[dict[str, Any]]:
        if not self._ddl_allowed():
            return []
        create_table_sql = self._create_table_sql_from_prompt()
        if create_table_sql:
            return [
                {
                    "title": "Create table from prompt",
                    "generatedSql": create_table_sql,
                    "explanation": "Creates a new table using sanitized identifiers from the prompt. Requires preview and confirmation.",
                    "warnings": ["DDL requires preview and explicit confirmation before execution."],
                }
            ]
        return []

    def _ddl_allowed(self) -> bool:
        for policy in active_policies_for_user(self.request.accessPolicies, self.request.verifiedUser):
            operations = {operation.upper() for operation in policy.allowedOperations}
            if "DDL" in operations:
                return True
        return False

    def _create_table_sql_from_prompt(self) -> str | None:
        prompt = self.request.prompt
        prompt_lower = prompt.lower()
        if not re.search(r"\bcreate\s+(?:a\s+)?table\b", prompt_lower):
            return None

        table_match = re.search(
            r"\bcreate\s+(?:a\s+)?table\s+(?:named\s+|called\s+)?([a-zA-Z_][a-zA-Z0-9_]*)",
            prompt,
            flags=re.IGNORECASE,
        )
        if not table_match:
            return None
        table_name = table_match.group(1)
        if not self._safe_identifier(table_name):
            return None

        columns_match = re.search(r"\bcolumns?\s*:?\s*(.+)$", prompt, flags=re.IGNORECASE)
        if not columns_match:
            return None
        raw_columns = re.split(r",|\band\b", columns_match.group(1), flags=re.IGNORECASE)
        columns = []
        for raw_column in raw_columns:
            column = raw_column.strip().strip(".;:")
            column = re.split(r"\s+", column)[0] if column else ""
            if column and self._safe_identifier(column) and column not in columns:
                columns.append(column)
        if not columns:
            return None

        column_definitions = []
        for column in columns:
            if column.lower() == "id":
                id_type = "INT" if self.dialect == "mysql" else "INTEGER"
                column_definitions.append(f"{column} {id_type} PRIMARY KEY")
            elif column.lower() in {"roll_no", "email"}:
                length = "50" if column.lower() == "roll_no" else "255"
                column_definitions.append(f"{column} VARCHAR({length}) NOT NULL UNIQUE")
            else:
                column_definitions.append(f"{column} VARCHAR(255) NOT NULL")
        return f"CREATE TABLE {table_name} ({', '.join(column_definitions)})"

    def _safe_identifier(self, value: str) -> bool:
        return bool(re.fullmatch(r"[A-Za-z_][A-Za-z0-9_]*", value or ""))

    def _is_ddl_intent(self) -> bool:
        prompt = self.request.prompt.lower()
        ddl_patterns = (
            r"\bcreate\s+(?:a\s+)?table\b",
            r"\bcreate\s+table\b",
            r"\balter\s+table\b",
            r"\bdrop\s+table\b",
            r"\btruncate\s+table\b",
            r"\bcreate\s+index\b",
            r"\bdrop\s+index\b",
        )
        return any(re.search(pattern, prompt) for pattern in ddl_patterns)

    def _is_database_admin_intent(self) -> bool:
        prompt = self.request.prompt.lower()
        admin_patterns = (
            r"\bcreate\s+database\b",
            r"\bdrop\s+database\b",
            r"\bcreate\s+user\b",
            r"\bdrop\s+user\b",
            r"\bcreate\s+role\b",
            r"\bdrop\s+role\b",
            r"\balter\s+system\b",
            r"\bgrant\b",
            r"\brevoke\b",
            r"\buse\s+[a-zA-Z_][a-zA-Z0-9_]*\b",
        )
        return any(re.search(pattern, prompt) for pattern in admin_patterns)

    def _row_policy_summary(self) -> list[dict[str, Any]]:
        return [
            {
                "tableName": table.get("tableName"),
                "rowAccessRule": table.get("rowAccessRule"),
            }
            for table in self.allowed_schema.get("allowedTables", [])
        ]

    def _best_table(self) -> dict[str, Any] | None:
        tables = self.allowed_schema.get("allowedTables", [])
        if not tables:
            return None
        prompt = self.request.prompt.lower()
        for table in tables:
            if table["tableName"].lower() in prompt:
                return table
        for table in tables:
            name = table["tableName"].lower()
            singular_name = name[:-1] if name.endswith("s") else name
            if singular_name and singular_name in prompt:
                return table
        return tables[0]

    def _table_name_from_prompt(self) -> str | None:
        patterns = (
            r"\btable\s+([A-Za-z_][A-Za-z0-9_]*)\b",
            r"\binto\s+([A-Za-z_][A-Za-z0-9_]*)\b",
            r"\bfrom\s+([A-Za-z_][A-Za-z0-9_]*)\b",
        )
        for pattern in patterns:
            match = re.search(pattern, self.request.prompt, flags=re.IGNORECASE)
            if match:
                return match.group(1)
        return None

    def _tables_used(self, sql: str) -> list[str]:
        try:
            expression = sqlglot.parse_one(sql, dialect=self.dialect)
        except sqlglot.errors.ParseError:
            return []
        return sorted({table.name for table in expression.find_all(exp.Table) if table.name})

    def _columns_used(self, sql: str) -> list[str]:
        try:
            expression = sqlglot.parse_one(sql, dialect=self.dialect)
        except sqlglot.errors.ParseError:
            return []
        return sorted({column.name for column in expression.find_all(exp.Column) if column.name != "*"})

    def _dedupe_key(self, sql: str) -> str:
        return re.sub(r"\s+", " ", sql.strip().lower())

    def _semantic_dedupe_key(self, sql: str) -> str:
        command_type = classify_sql_command(sql)
        if command_type == "INSERT":
            table_name, columns = self._insert_target_and_columns(sql)
            row_count = self._insert_row_count(sql)
            if table_name and columns:
                return f"insert:{table_name.lower()}:{','.join(column.lower() for column in columns)}:rows:{row_count}"
        normalized = self._dedupe_key(sql)
        normalized = re.sub(r"'(?:''|[^'])*'", "?", normalized)
        normalized = re.sub(r'"(?:""|[^"])*"', "?", normalized)
        normalized = re.sub(r"\b\d+(?:\.\d+)?\b", "?", normalized)
        return normalized

    def _title_for(self, query_type: str) -> str:
        return f"{query_type.title()} query option"

    def _risk_level(self, query_type: str) -> str:
        if query_type in {"UPDATE", "DELETE", "INSERT"}:
            return "high"
        if query_type == "SELECT":
            return "low"
        return "medium"

    def _unique_strings(self, values: list[str]) -> list[str]:
        unique: list[str] = []
        for value in values:
            if value and value not in unique:
                unique.append(value)
        return unique

    def _select_columns(self, allowed_columns: list[str], preferred_columns: list[str]) -> str:
        selected = [column for column in preferred_columns if column in allowed_columns]
        if not selected:
            selected = allowed_columns[:5]
        return ", ".join(selected) if selected else "*"

    def _has_column(self, columns: list[str], column_name: str) -> bool:
        return column_name in {column.lower() for column in columns}

    def _first_existing_column(self, columns: list[str], candidates: list[str]) -> str | None:
        lower_columns = {column.lower(): column for column in columns}
        for candidate in candidates:
            if candidate in lower_columns:
                return lower_columns[candidate]
        return None

    def _insert_records_option(self, table: dict[str, Any]) -> dict[str, Any] | None:
        table_name = table.get("tableName")
        if not table_name:
            return None
        insert_columns = self._required_columns_for_insert(table)
        if not insert_columns:
            insert_columns = table.get("allowedColumns", [])[:4]
        if not insert_columns:
            return None

        count = self._extract_record_count(self.request.prompt.lower()) or 5
        count = max(1, min(count, 20))
        column_names = [column["name"] for column in insert_columns]
        rows = []
        for row_number in range(1, count + 1):
            values = [self._sample_value_for_column(column, row_number) for column in insert_columns]
            rows.append(f"({', '.join(values)})")
        return {
            "title": f"Insert {count} {table_name} records",
            "generatedSql": f"INSERT INTO {table_name} ({', '.join(column_names)}) VALUES {', '.join(rows)}",
            "explanation": (
                f"Inserts {count} rows using required columns from the actual {table_name} schema. "
                "Requires preview and confirmation before execution."
            ),
            "warnings": ["Values are safe sample data. Review and edit the prompt if you need different data."],
        }

    def _required_columns_for_insert(self, table: dict[str, Any]) -> list[dict[str, Any]]:
        required = [column for column in table.get("allowedColumns", []) if column.get("requiredForInsert")]
        if required:
            return required
        return [
            column
            for column in table.get("allowedColumns", [])
            if not column.get("nullable", True) and column.get("default") is None
        ]

    def _missing_required_insert_columns(self, sql: str) -> list[str]:
        table_name, inserted_columns = self._insert_target_and_columns(sql)
        if not table_name or not inserted_columns:
            return []
        table = self._table_schema_for(table_name)
        if not table:
            return []
        required_columns = {column["name"].lower() for column in self._required_columns_for_insert(table)}
        return sorted(required_columns - {column.lower() for column in inserted_columns})

    def _insert_target_and_columns(self, sql: str) -> tuple[str, list[str]]:
        match = re.search(
            r"\bINSERT\s+INTO\s+([A-Za-z_][A-Za-z0-9_]*)\s*\(([^)]*)\)",
            sql,
            flags=re.IGNORECASE | re.DOTALL,
        )
        if not match:
            return "", []
        columns = [
            value.strip().strip('"`[]')
            for value in match.group(2).split(",")
            if value.strip()
        ]
        return match.group(1), columns

    def _insert_row_count(self, sql: str) -> int:
        try:
            expression = sqlglot.parse_one(sql, dialect=self.dialect)
            values = expression.find(exp.Values)
            if values is not None and values.expressions:
                return len(values.expressions)
        except sqlglot.errors.ParseError:
            return 1
        return 1

    def _table_schema_for(self, table_name: str) -> dict[str, Any] | None:
        for table in self.allowed_schema.get("allowedTables", []):
            if table.get("tableName", "").lower() == table_name.lower():
                return table
        return None

    def _sample_value_for_column(self, column: dict[str, Any], row_number: int) -> str:
        name = column.get("name", "").lower()
        column_type = column.get("type", "").upper()
        if name in {"id", "student_id", "employee_id"} or column_type.startswith(("INT", "BIGINT", "SMALLINT")):
            return str(row_number)
        if "roll" in name:
            return self._sql_string(f"R{row_number:03d}")
        if "email" in name:
            return self._sql_string(f"student{row_number}@example.com")
        if "name" in name:
            return self._sql_string(f"Student {row_number}")
        if "DATE" in column_type or name.endswith("_date"):
            return self._sql_string(f"2026-01-{row_number:02d}")
        if any(token in column_type for token in ("DECIMAL", "NUMERIC", "FLOAT", "DOUBLE", "REAL")):
            return str(row_number)
        return self._sql_string(f"{column.get('name', 'value')}_{row_number}")

    def _sql_string(self, value: str) -> str:
        return "'" + value.replace("'", "''") + "'"

    def _extract_number_after(self, prompt: str, keyword: str) -> float | None:
        match = re.search(rf"{keyword}\D+(\d+(?:\.\d+)?)", prompt)
        return float(match.group(1)) if match else None

    def _extract_record_count(self, prompt: str) -> int | None:
        match = re.search(r"\b(\d+)\s+(?:records?|rows?)\b", prompt)
        return int(match.group(1)) if match else None

    def _extract_top_n(self, prompt: str) -> int | None:
        match = re.search(r"\btop\s+(\d+)", prompt)
        if not match:
            return None
        return max(1, min(int(match.group(1)), 100))

    def _extract_percentage(self, prompt: str) -> float | None:
        match = re.search(r"(\d+(?:\.\d+)?)\s*%", prompt)
        return float(match.group(1)) if match else None
