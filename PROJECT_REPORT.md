# Secure AI-Based Natural Language to SQL Query Generator with Role-Based Access Control and Safe Query Execution

## 1. Abstract

The Secure AI-Based Natural Language to SQL Query Generator is a web-based college project that allows users to convert natural language requests into SQL query options. The system is designed with strong security controls so that users can access only the data they are authorized to view or modify.

The application uses FastAPI for the backend, SQLAlchemy with SQLite for database management, JWT authentication, bcrypt password hashing, sqlglot for SQL parsing and validation, and the Gemini API for AI-assisted SQL generation. The frontend is built using HTML, CSS, and vanilla JavaScript.

Unlike a basic SQL generator, this project does not directly trust AI output. The generated SQL is treated as untrusted input. Before any query is previewed or executed, the backend validates the SQL syntax, checks the user's role permissions, applies row-level security, blocks dangerous commands, and records important events in audit logs. The system also provides multiple suitable SQL alternatives so the user can select the most appropriate query before preview or execution.

This project demonstrates a safe approach to AI-assisted database access by combining natural language processing, role-based access control, query validation, row-level security, impact analysis, confirmation workflows, and audit logging.

## 2. Problem Statement

Natural language to SQL systems make databases easier to use because users can ask questions in simple English instead of writing SQL manually. However, these systems can create serious security risks if the generated SQL is executed without proper checks.

Common risks include:

- A user may access private records belonging to another user.
- A manager may accidentally or intentionally access another department's data.
- A student may view another student's academic records.
- AI may generate unsafe SQL that includes restricted tables or columns.
- SQL injection or multiple-statement attacks may be attempted.
- UPDATE or DELETE queries may affect more records than expected.
- TCL commands may interfere with transactions if executed.
- DCL or dangerous DDL commands may alter permissions or database structure.
- Frontend-only restrictions may be bypassed by direct API calls.
- Sensitive information may be stored in logs.

This project solves these problems by ensuring that all security decisions are made on the backend. The system validates, authorizes, previews, confirms, executes, and audits queries through a controlled workflow.

## 3. Project Objectives

The main objectives of this project are:

- To build a beginner-friendly AI SQL query generator.
- To allow users to enter natural language prompts and receive multiple SQL query alternatives.
- To require the user to select one generated query option before preview and execution.
- To implement secure login using JWT tokens and bcrypt password hashing.
- To implement role-based access control for admin, manager, employee, faculty, and student users.
- To ensure users can see only their own authorized data.
- To ensure managers can see only employee records from their own department.
- To ensure students can see only their own student records.
- To dynamically show only the database schema that each user is allowed to access.
- To validate SQL using sqlglot before preview and again before execution.
- To block unsafe SQL commands and suspicious SQL patterns.
- To treat TCL commands as view-only learning examples that can never execute.
- To block DCL and dangerous DDL commands.
- To require preview and confirmation before UPDATE and DELETE queries.
- To record all important activities in audit logs.
- To provide a clean frontend suitable for project demonstration.

## 4. Functional Requirements

The functional requirements of the system are:

- The system shall allow users to log in using a username and password.
- The system shall issue JWT access tokens after successful login.
- The system shall hash passwords using bcrypt before storing them.
- The system shall provide a protected `/me` endpoint to show the current user.
- The system shall provide a role-based `/schema` endpoint.
- The system shall hide restricted tables and columns from unauthorized users.
- The system shall accept a natural language prompt from a logged-in user.
- The system shall generate two or three meaningful SQL query alternatives when possible.
- The system shall show query title, SQL, query type, tables used, columns used, explanation, risk level, warnings, and execution status.
- The system shall require the user to select exactly one query option before preview.
- The system shall save selected queries temporarily on the server side.
- The system shall preview SELECT queries by returning estimated row count and up to 20 rows.
- The system shall preview UPDATE and DELETE queries without modifying data.
- The system shall require explicit confirmation for UPDATE, INSERT, and DELETE queries when allowed.
- The system shall execute SELECT queries only after validation and authorization.
- The system shall execute UPDATE and DELETE queries only after preview and confirmation.
- The system shall never execute TCL commands.
- The system shall block DCL commands.
- The system shall block dangerous DDL commands.
- The system shall store query history for each user.
- The system shall allow users to view only their own query history.
- The system shall allow admins to view audit logs.
- The system shall prevent non-admin users from viewing audit logs.

## 5. Non-Functional Requirements

The non-functional requirements of the system are:

- Security: The system must prevent unauthorized data access and unsafe query execution.
- Reliability: The system must validate and authorize queries before preview and again before execution.
- Usability: The frontend must be simple, clean, and suitable for a college project demonstration.
- Maintainability: The backend code must be modular and beginner-friendly.
- Auditability: Important actions must be recorded in audit logs.
- Privacy: Passwords, JWT tokens, and secrets must not be stored in logs.
- Performance: The system should limit preview and execution result sizes to avoid excessive data exposure.
- Portability: The project should run locally using SQLite for development.
- Extensibility: The module structure should allow future improvements such as production database support and advanced query planning.

## 6. Technology Stack

| Layer | Technology |
| --- | --- |
| Backend Framework | FastAPI |
| Programming Language | Python 3 |
| ORM | SQLAlchemy |
| Development Database | SQLite |
| Authentication | JWT with OAuth2PasswordBearer |
| Password Hashing | bcrypt using Passlib |
| SQL Parsing and Validation | sqlglot |
| AI Integration | Gemini API |
| Frontend | HTML, CSS, Vanilla JavaScript |
| Testing | pytest and FastAPI TestClient |
| Environment Variables | python-dotenv |

## 7. System Architecture

The system follows a client-server architecture.

The frontend provides the user interface for login, natural language prompt entry, query option selection, preview, execution, history, and security status. The frontend sends requests to the FastAPI backend and includes the JWT token in the `Authorization: Bearer <token>` header for protected API calls.

The backend performs all important security checks. It authenticates users, reads the database schema according to the user's role, sends allowed schema information to the AI generator, stores generated query options, validates SQL, applies row-level restrictions, previews query impact, executes safe queries, and records audit logs.

The database stores users, employees, students, selected queries, query history, and audit logs. SQLite is used for development and demonstration.

High-level workflow:

1. User logs in and receives a JWT token.
2. User enters a natural language prompt.
3. Backend reads the user's allowed schema.
4. AI or fallback logic generates multiple SQL alternatives.
5. Backend stores generated options server-side.
6. User selects one option.
7. Backend retrieves the selected option from server-side storage.
8. Backend validates and authorizes the SQL before preview.
9. Backend applies row-level security and returns preview results.
10. User confirms execution if required.
11. Backend validates, authorizes, and enforces row-level security again.
12. Backend executes only safe and allowed queries.
13. Query history and audit logs are recorded.

## 8. Module Description

### Authentication Module

The Authentication Module handles user registration, login, password hashing, and JWT token creation. Passwords are hashed using bcrypt before storage. During login, the submitted password is verified against the stored password hash. If login succeeds, the backend returns a JWT access token.

This module ensures that protected endpoints can be accessed only by authenticated users. It also ensures password hashes are never returned in API responses.

### Authorization and RBAC Module

The Authorization and Role-Based Access Control Module defines the permissions of each role. The supported roles are admin, manager, employee, faculty, and student.

This module decides:

- Which tables a user can access.
- Which columns a user can access.
- Which query types a user can execute.
- What row-level rule applies to the user.

For example, employees can access only their own Employee record, managers can access only Employee records in their own department, and students can access only their own Students record.

### Schema Reader Module

The Schema Reader Module dynamically reads the database schema using SQLAlchemy. It returns only the schema that the logged-in user is allowed to see.

For example:

- Employee users can see safe Employee columns but not `manager_id`.
- Student users can see safe Students columns but not `faculty_id`.
- Admin users can see all allowed Employee and Students columns.
- Internal tables such as QueryHistory and AuditLogs are not exposed through the schema endpoint.
- `Users.password_hash` is never exposed.

### AI SQL Generator Module

The AI SQL Generator Module accepts a natural language prompt and generates SQL query options. The backend sends only the user's allowed schema, role, allowed tables, allowed columns, and row-level restriction information to the AI.

The AI must return valid JSON containing query options. The module also includes a rule-based fallback generator for common requests such as salary filters, top students by CGPA, employee department filtering, counts, grouped summaries, salary updates, and conditional deletes.

The AI output is never trusted directly. It is only treated as a proposed query that must pass validation and authorization later.

### SQL Validator Module

The SQL Validator Module uses sqlglot to parse, classify, normalize, and validate SQL.

It classifies SQL into:

- SELECT
- INSERT
- UPDATE
- DELETE
- TCL
- DCL
- DDL
- UNKNOWN

It rejects unsafe cases such as multiple SQL statements, comments used to bypass checks, restricted tables, restricted columns, UPDATE without WHERE, DELETE without WHERE, unknown commands, and dangerous DDL or DCL commands.

### Row-Level Security Module

The Row-Level Security Module applies server-side filters to ensure users can access only authorized rows.

Examples:

- Employee users receive an `employee_id = current_user.employee_id` filter.
- Student users receive a `student_id = current_user.student_id` filter.
- Manager users receive a `department = current_user.department` filter.
- Faculty users receive a `faculty_id = current_user.user_id` filter.

If a query already contains a WHERE clause, the row-level condition is combined safely with the existing condition.

### Query Alternatives Module

The Query Alternatives Module provides multiple possible SQL options for a single natural language prompt. These alternatives may differ in detail level, selected columns, aggregation, or filtering.

For example, for a prompt like "Show employees whose salary is greater than 50000", the system may generate:

- A detailed employee records query.
- A query with only basic employee columns.
- A grouped or count-based summary query.

The user must select one query option before preview and execution. This helps the user understand and choose the most suitable query.

### Query Impact Analyzer Module

The Query Impact Analyzer Module previews the selected query before execution.

For SELECT queries, it returns:

- A safe preview query.
- Estimated row count.
- Up to 20 preview rows.

For UPDATE and DELETE queries, it does not execute the write query. Instead, it creates a safe SELECT preview using the same WHERE condition and row-level restrictions. It returns the estimated number of affected rows and sample records that would be modified or deleted.

This module marks UPDATE and DELETE queries as requiring confirmation.

### Safe Execution Module

The Safe Execution Module executes only validated and authorized SQL. It repeats validation and row-level enforcement before execution, even if the query was already previewed.

Execution rules include:

- SELECT can execute after validation and authorization.
- INSERT is admin-only and requires confirmation.
- UPDATE is admin or authorized-manager only, requires WHERE, successful preview, and confirmation.
- DELETE is admin-only, requires WHERE, successful preview, and confirmation.
- TCL commands are never executed.
- DCL commands are blocked.
- Dangerous DDL commands are blocked.

This module also records execution attempts in query history and audit logs.

### Query History and Audit Log Module

The Query History and Audit Log Module records user activity for accountability.

Query history allows users to see their own past query prompts, selected SQL, query type, status, affected rows, and timestamp.

Audit logs record important security events such as login success, login failure, schema access, query generation, query selection, validation failure, authorization failure, preview, execution attempt, successful execution, blocked TCL, blocked DCL, blocked DDL, and suspicious SQL attempts.

Passwords, JWT tokens, and secrets are not intentionally stored in logs. The audit logger also redacts common sensitive patterns.

## 9. Database Design

The database contains the following main tables:

### Users

| Column | Description |
| --- | --- |
| user_id | Primary key |
| username | Unique username |
| password_hash | bcrypt password hash |
| role | User role |
| department | User department, if applicable |
| employee_id | Linked employee ID, if applicable |
| student_id | Linked student ID, if applicable |
| created_at | Account creation time |

### Employee

| Column | Description |
| --- | --- |
| employee_id | Primary key |
| name | Employee name |
| email | Unique email |
| department | Department name |
| salary | Employee salary |
| joining_date | Joining date |
| manager_id | Manager ID |

### Students

| Column | Description |
| --- | --- |
| student_id | Primary key |
| name | Student name |
| email | Unique email |
| course | Course name |
| cgpa | Student CGPA |
| faculty_id | Assigned faculty user ID |

### QueryHistory

| Column | Description |
| --- | --- |
| history_id | Primary key |
| user_id | User who generated or executed the query |
| user_prompt | Natural language prompt |
| selected_option_id | Selected query option ID |
| generated_sql | AI-generated SQL |
| final_enforced_sql | SQL after security enforcement |
| query_type | SQL command type |
| execution_status | Generated, previewed, executed, or blocked |
| rows_affected | Number of affected rows |
| created_at | Timestamp |

### SelectedQueries

| Column | Description |
| --- | --- |
| selected_query_id | Primary key |
| user_id | User who selected the query |
| option_id | Selected option ID |
| title | Query title |
| generated_sql | Server-saved generated SQL |
| query_type | SQL command type |
| created_at | Selection time |
| expires_at | Expiry time |

### AuditLogs

| Column | Description |
| --- | --- |
| log_id | Primary key |
| user_id | User related to the event |
| action_type | Type of audited action |
| user_prompt | Prompt, if applicable |
| generated_sql | Generated SQL, if applicable |
| final_enforced_sql | Security-enforced SQL, if applicable |
| query_type | SQL command type |
| execution_status | Status of the event |
| rows_affected | Affected rows |
| created_at | Timestamp |

## 10. User Roles and Permissions Table

| Role | Data Access | Allowed Query Types | Special Rules |
| --- | --- | --- | --- |
| Admin | Can view all allowed Employee and Students rows | SELECT, INSERT, UPDATE, DELETE | DCL, dangerous DDL, and TCL execution are still blocked |
| Manager | Can view Employee records only from own department | SELECT, limited UPDATE | Cannot DELETE; UPDATE must be scoped to own department and requires preview and confirmation |
| Employee | Can view only own Employee record | SELECT only | Cannot INSERT, UPDATE, or DELETE |
| Faculty | Can view only Students assigned to the faculty user | SELECT only | Cannot access unrelated students |
| Student | Can view only own Students record | SELECT only | Cannot access another student's record |

## 11. SQL Command Execution Policy Table

| SQL Command Type | Policy | Execution Allowed |
| --- | --- | --- |
| SELECT | Allowed after validation, authorization, and row-level enforcement | Yes |
| INSERT | Allowed only for admin after validation and confirmation | Yes, admin only |
| UPDATE | Allowed for admin or authorized manager only; WHERE, preview, and confirmation required | Yes, restricted |
| DELETE | Allowed only for admin; WHERE, preview, and confirmation required | Yes, admin only |
| TCL | Shown only for learning and explanation | No |
| DCL | Permission changes are blocked | No |
| Dangerous DDL | Schema changes such as DROP, ALTER, CREATE, TRUNCATE, ATTACH, and PRAGMA are blocked | No |
| UNKNOWN | Rejected | No |

## 12. API Endpoints

| Endpoint | Method | Purpose | Authentication Required |
| --- | --- | --- | --- |
| `/health` | GET | Check backend and database health | No |
| `/register` | POST | Register a test user | No |
| `/login` | POST | Login and receive JWT token | No |
| `/me` | GET | Get current logged-in user | Yes |
| `/schema` | GET | Get role-based visible schema | Yes |
| `/generate` | POST | Generate SQL query alternatives | Yes |
| `/select-query` | POST | Select one generated query option | Yes |
| `/selected-query` | GET | View current selected query | Yes |
| `/preview-selected-query` | POST | Preview selected query safely | Yes |
| `/execute-selected-query` | POST | Execute selected query safely | Yes |
| `/history` | GET | View current user's query history | Yes |
| `/admin/audit-logs` | GET | View audit logs with filters | Yes, admin only |

## 13. Security Features

The project includes the following security features:

- JWT authentication for protected routes.
- bcrypt password hashing.
- No password hash exposure in API responses.
- Role-based access control.
- Row-level security for employees, managers, faculty, and students.
- Dynamic schema filtering based on user role.
- Server-side storage of generated and selected query options.
- AI output treated as untrusted input.
- SQL validation before preview.
- SQL validation again before execution.
- SQL syntax parsing using sqlglot.
- Multiple SQL statements rejected.
- SQL comments rejected.
- Restricted tables blocked.
- Restricted columns blocked.
- UPDATE without WHERE rejected.
- DELETE without WHERE rejected.
- TCL commands are view-only and cannot execute.
- DCL commands are blocked.
- Dangerous DDL commands are blocked.
- UPDATE and DELETE require preview and confirmation.
- Preview does not modify data.
- SELECT result size is limited.
- Audit logs record important events.
- Audit logger redacts common sensitive values.
- Frontend escapes displayed text to reduce HTML injection risk.
- Frontend hides or disables buttons based on backend responses, but backend remains the real security authority.

## 14. Test Cases

| Test Case | Expected Result |
| --- | --- |
| Valid login | User receives JWT access token |
| Invalid password | Login fails with unauthorized response |
| Protected endpoint without token | Request is rejected |
| Invalid or expired token | Request is rejected |
| Password hash in response | Password hash is never returned |
| Employee tries to view another employee | Access is blocked or row-level filter returns no unauthorized rows |
| Student tries to view another student | Access is blocked or row-level filter returns no unauthorized rows |
| Manager views another department | Access is blocked by department filter |
| Faculty views unassigned students | Access is blocked by faculty filter |
| Admin views allowed employee/student rows | Access is allowed |
| Valid SELECT query | Query is accepted after validation |
| UPDATE without WHERE | Query is rejected |
| DELETE without WHERE | Query is rejected |
| Multiple SQL statements | Query is rejected |
| SQL comments used for bypass | Query is rejected |
| DDL command | Query is blocked |
| DCL command | Query is blocked |
| TCL command | Shown as view-only and never executed |
| Restricted column access | Query is rejected |
| Restricted table access | Query is rejected |
| UPDATE preview | Data is not modified |
| DELETE preview | Data is not deleted |
| UPDATE without confirmation | Execution is blocked |
| DELETE without confirmation | Execution is blocked |
| User history access | User sees only own history |
| Admin audit log access | Admin can view audit logs |
| Non-admin audit log access | Access is denied |
| Audit log redaction | Passwords, tokens, and secrets are redacted |

## 15. Sample Inputs and Outputs

### Sample Login Input

```json
{
  "username": "employee_6",
  "password": "employee123"
}
```

### Sample Login Output

```json
{
  "access_token": "jwt_token_here",
  "token_type": "bearer",
  "role": "employee",
  "username": "employee_6"
}
```

### Sample Natural Language Prompt

```json
{
  "prompt": "Show employees whose salary is greater than 50000"
}
```

### Sample Generated Query Options Output

```json
{
  "user_prompt": "Show employees whose salary is greater than 50000",
  "query_options": [
    {
      "option_id": 1,
      "title": "Detailed employee records",
      "sql": "SELECT employee_id, name, email, department, salary, joining_date FROM employees WHERE salary > 50000",
      "query_type": "SELECT",
      "tables_used": ["employees"],
      "columns_used": ["employee_id", "name", "email", "department", "salary", "joining_date"],
      "explanation": "Shows employee records with salary greater than the selected value.",
      "risk_level": "low",
      "execution_allowed": true,
      "requires_confirmation": false,
      "warnings": []
    },
    {
      "option_id": 2,
      "title": "Basic employee salary list",
      "sql": "SELECT employee_id, name, salary FROM employees WHERE salary > 50000",
      "query_type": "SELECT",
      "tables_used": ["employees"],
      "columns_used": ["employee_id", "name", "salary"],
      "explanation": "Shows a smaller set of columns for salary review.",
      "risk_level": "low",
      "execution_allowed": true,
      "requires_confirmation": false,
      "warnings": []
    }
  ]
}
```

### Sample Select Query Input

```json
{
  "option_id": 1,
  "title": "Detailed employee records",
  "sql": "SELECT employee_id, name, email, department, salary, joining_date FROM employees WHERE salary > 50000",
  "query_type": "SELECT"
}
```

Even though the frontend sends SQL, the backend does not trust it. The backend selects the matching option from the last server-saved generated query response.

### Sample Preview Output for Employee User

```json
{
  "selected_option_id": 1,
  "generated_sql": "SELECT employee_id, name, email, department, salary, joining_date FROM employees WHERE salary > 50000",
  "final_enforced_sql": "SELECT employee_id, name, email, department, salary, joining_date FROM employees WHERE salary > 50000 AND employee_id = 6",
  "preview_sql": "SELECT * FROM (SELECT employee_id, name, email, department, salary, joining_date FROM employees WHERE salary > 50000 AND employee_id = 6) AS preview_source LIMIT 20",
  "query_type": "SELECT",
  "estimated_rows": 1,
  "preview_rows": [
    {
      "employee_id": 6,
      "name": "Sample Employee",
      "email": "employee6@example.com",
      "department": "IT",
      "salary": 62000,
      "joining_date": "2022-04-10"
    }
  ],
  "impact_message": "SELECT preview is limited to 20 rows.",
  "risk_level": "low",
  "execution_allowed": true,
  "requires_confirmation": false,
  "warnings": []
}
```

### Sample TCL Output

```json
{
  "query_type": "TCL",
  "execution_allowed": false,
  "impact_message": "Transaction control commands are shown for explanation only and are never executed."
}
```

## 16. Limitations

The current limitations of the project are:

- SQLite is used for development and demonstration only.
- Demo user passwords are simple for easy testing.
- Registration is open for testing and should be admin-only in production.
- The frontend stores JWT tokens in `sessionStorage` for demo purposes.
- CORS is permissive for local development.
- Complex joins and unions are blocked in this beginner-friendly version.
- The project does not include deployment configuration for a production server.
- The AI quality depends on the Gemini API response and prompt design.

## 17. Future Enhancements

Possible future enhancements include:

- Add production database support such as PostgreSQL.
- Add database migrations using Alembic.
- Make user registration admin-only.
- Add password reset and account lockout features.
- Add rate limiting for login and query generation.
- Add HTTPS deployment and secure cookie-based authentication.
- Add advanced SQL join support with stronger formal row-level validation.
- Add query cost estimation and explain-plan support.
- Add an admin dashboard for audit log analysis.
- Add export options for query results.
- Add more detailed AI prompt safety policies.
- Add support for more database engines.

## 18. Conclusion

The Secure AI-Based Natural Language to SQL Query Generator demonstrates how AI can be used to make database querying easier while still maintaining strong security controls. The project allows users to generate multiple SQL alternatives from natural language prompts, select one option, preview the effect, and execute only safe and authorized queries.

The system ensures that users can see only their own authorized data. Managers are restricted to their department data, students are restricted to their own records, and faculty members are restricted to assigned students. TCL commands are shown only for learning and cannot execute, while DCL and dangerous DDL commands are blocked. UPDATE and DELETE operations require preview and confirmation. All important activities are recorded in audit logs.

Overall, this project provides a practical example of combining AI-assisted SQL generation with authentication, authorization, row-level security, validation, safe execution, and auditing. It is suitable as a college final project because it demonstrates both modern AI integration and important software security principles.
