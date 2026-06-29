# Ubuntu VPS Production Deployment

This guide deploys the refactored architecture on a cloud Ubuntu VPS using Docker Compose.

## Production Services

- `client`: React build served by Nginx.
- `server`: Node.js + Express API.
- `sql-service`: Python FastAPI SQL intelligence service.
- `postgres`: PostgreSQL target database.
- `mysql`: MySQL target database.
- `mongo`: MongoDB metadata database, optional if you use MongoDB Atlas.

Only the Nginx container publishes ports to the internet. Express, FastAPI, PostgreSQL, MySQL, and MongoDB stay on the internal Docker network.

## Security Model

- React calls only `/api` on Nginx.
- Nginx proxies `/api` to Express over the internal Docker network.
- Express calls `sql-service` through `http://sql-service:8001`.
- Express sends `x-internal-api-key` to the Python service.
- PostgreSQL and MySQL do not publish public ports.
- Normal SQL execution uses restricted accounts: `POSTGRES_APP_URL` and `MYSQL_APP_URL`.
- Admin infrastructure actions use separate privileged accounts: `POSTGRES_ADMIN_URL` and `MYSQL_ADMIN_URL`.
- The only allow-listed infrastructure DDL action is `CREATE DATABASE database_name`.
- `DROP DATABASE`, `CREATE ROLE`, `ALTER SYSTEM`, `GRANT`, `REVOKE`, root/superuser normal queries, and unsafe infrastructure commands are blocked.

## 1. Prepare the VPS

SSH into the VPS.

```bash
ssh ubuntu@your-server-ip
```

Install Docker and the Compose plugin.

```bash
sudo apt update
sudo apt install -y ca-certificates curl gnupg
sudo install -m 0755 -d /etc/apt/keyrings
curl -fsSL https://download.docker.com/linux/ubuntu/gpg | sudo gpg --dearmor -o /etc/apt/keyrings/docker.gpg
sudo chmod a+r /etc/apt/keyrings/docker.gpg
echo "deb [arch=$(dpkg --print-architecture) signed-by=/etc/apt/keyrings/docker.gpg] https://download.docker.com/linux/ubuntu $(. /etc/os-release && echo "$VERSION_CODENAME") stable" | sudo tee /etc/apt/sources.list.d/docker.list >/dev/null
sudo apt update
sudo apt install -y docker-ce docker-ce-cli containerd.io docker-buildx-plugin docker-compose-plugin
sudo usermod -aG docker "$USER"
```

Log out and log back in so the Docker group change applies.

## 2. Configure Firewall

Open only SSH, HTTP, and HTTPS.

```bash
sudo ufw allow OpenSSH
sudo ufw allow 80/tcp
sudo ufw allow 443/tcp
sudo ufw enable
sudo ufw status
```

Do not open `5000`, `8001`, `5432`, `3306`, or `27017` publicly.

## 3. Upload or Clone the Project

```bash
git clone <your-repository-url>
cd secure-ai-sql-query-generator
```

## 4. Create Production Environment File

```bash
cp .env.production.example .env.production
nano .env.production
```

Use strong secrets. Example shapes are shown below, but do not copy these exact values.

```env
PUBLIC_ORIGIN=https://your-domain.example.com
VITE_API_BASE_URL=/api

MONGODB_URI=mongodb://mongo:27017/sql-query-generator
JWT_SECRET=replace-with-a-long-random-secret
SQL_SERVICE_API_KEY=replace-with-a-long-random-internal-key
GEMINI_API_KEY=replace-with-provider-key
GEMINI_MODEL=gemini-2.5-flash

POSTGRES_BOOTSTRAP_DB=postgres
POSTGRES_BOOTSTRAP_USER=postgres
POSTGRES_BOOTSTRAP_PASSWORD=replace-bootstrap-password
POSTGRES_APP_DB=company_app
POSTGRES_APP_USER=company_app_user
POSTGRES_APP_PASSWORD=replace-app-password
POSTGRES_APP_URL=postgresql+psycopg://company_app_user:replace-app-password@postgres:5432/company_app
POSTGRES_ADMIN_USER=company_admin_ddl
POSTGRES_ADMIN_PASSWORD=replace-admin-password
POSTGRES_ADMIN_URL=postgresql+psycopg://company_admin_ddl:replace-admin-password@postgres:5432/postgres

MYSQL_ROOT_PASSWORD=replace-root-bootstrap-password
MYSQL_APP_DATABASE=company_app
MYSQL_APP_USER=company_app_user
MYSQL_APP_PASSWORD=replace-app-password
MYSQL_APP_URL=mysql+pymysql://company_app_user:replace-app-password@mysql:3306/company_app
MYSQL_ADMIN_USER=company_admin_ddl
MYSQL_ADMIN_PASSWORD=replace-admin-password
MYSQL_ADMIN_URL=mysql+pymysql://company_admin_ddl:replace-admin-password@mysql:3306/mysql
```

If you use MongoDB Atlas, replace `MONGODB_URI` with the Atlas URI and optionally remove or ignore the `mongo` service.

## 5. TLS Certificates

For first deployment testing, you can use HTTP on port 80.

For HTTPS, obtain certificates with your preferred method and place them here:

```text
deploy/nginx/certs/fullchain.pem
deploy/nginx/certs/privkey.pem
```

Then uncomment the HTTPS server block in `deploy/nginx/default.conf`.

## 6. Start Production Containers

```bash
docker compose --env-file .env.production -f docker-compose.production.yml up -d --build
```

Check status.

```bash
docker compose --env-file .env.production -f docker-compose.production.yml ps
```

View logs.

```bash
docker compose --env-file .env.production -f docker-compose.production.yml logs -f server
docker compose --env-file .env.production -f docker-compose.production.yml logs -f sql-service
```

## 7. Seed MongoDB Metadata

After the server starts, seed demo users and database connection metadata.

```bash
docker compose --env-file .env.production -f docker-compose.production.yml exec server npm run seed
```

Database connection documents should store credential environment variable names such as `POSTGRES_APP_URL` or `MYSQL_APP_URL`, not actual database passwords or connection URLs.

## 8. Backups

Backups are written to the local `backups/` folder and should be copied to external storage.

```bash
./deploy/backups/backup-all.sh
./deploy/backups/backup-postgres.sh
./deploy/backups/backup-mysql.sh
```

Example daily cron job:

```cron
30 2 * * * cd /home/ubuntu/secure-ai-sql-query-generator && ./deploy/backups/backup-all.sh >> backups/backup.log 2>&1
```

## 9. Update Deployment

```bash
git pull
docker compose --env-file .env.production -f docker-compose.production.yml up -d --build
```

## 10. Verification Checklist

- `http://your-domain` loads the React website.
- `GET /api/auth/me` returns `401` without a token.
- Express logs show `SQL_SERVICE_URL=http://sql-service:8001`.
- PostgreSQL and MySQL ports are not open publicly.
- `docker volume ls` shows `postgres-data` and `mysql-data`.
- Normal target database connections use restricted app users.
- Admin DDL uses only the separate admin URLs.
- Backups produce `.sql.gz` files.
