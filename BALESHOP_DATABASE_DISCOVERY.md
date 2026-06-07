# Baleshop Database Discovery

## Summary

Baleshop / Yenkasa Store is not stored in MongoDB. It is a Spring Boot service backed by a local MySQL database on the DigitalOcean droplet.

The database is currently local-only and cannot be reached directly from Cloud Run.

## Server

- Public IP: `134.209.182.39`
- Private IP observed on server: `10.16.0.5`
- App directory: `/root/triciabales`
- PM2 app name: `tricia-bales-api`
- Spring Boot artifact: `target/baleshop-0.0.1-SNAPSHOT.jar`
- YenkasaChat proxy file: `/Users/kofibright/yenkasaChat/yenkasaChatBackend/RegLoginBackend/store/yenkasa-store-server.js`
- Proxy upstream env var: `TRICIABALES_API_BASE`
- Proxy fallback: `http://134.209.182.39:8080`

## Spring Datasource

Confirmed datasource in `/root/triciabales/src/main/resources/application.properties`:

- JDBC URL: `jdbc:mysql://localhost:3306/bale_shop`
- Driver: `com.mysql.cj.jdbc.Driver`
- Database user: `balesuser`
- Database name: `bale_shop`

Sensitive values are intentionally not recorded in this document.

## MySQL Server

- Server version: MySQL `8.0.46-0ubuntu0.24.04.2`
- `bind_address`: `127.0.0.1`

Because MySQL is bound to `127.0.0.1`, only processes on the Baleshop droplet can connect to it. Cloud Run cannot connect directly to this MySQL server.

## Databases

Confirmed databases:

- `bale_shop`
- `information_schema`
- `performance_schema`

## Table Inventory

Database: `bale_shop`

| Table | Approx. Rows |
| --- | ---: |
| `app_notifications` | 134 |
| `bale_images` | 101 |
| `bales` | 44 |
| `order_items` | 12 |
| `order_refunds` | 2 |
| `orders` | 12 |
| `user_tokens` | 35 |
| `users` | 20 |

## Application Storage Model

Based on Spring entities and live tables:

- Users: `users`
- User sessions/tokens: `user_tokens`
- Store products/bales: `bales`
- Product images: `bale_images`
- Orders: `orders`
- Order line items: `order_items`
- Refunds: `order_refunds`
- Notifications: `app_notifications`

## DatabaseAgent Integration Status

YenkasaCode Agent now has optional read-only SQL support for Baleshop:

- Env var: `BALESHOP_DATABASE_URL`
- Display label: `yenkasa_store`
- Expected URL format: `mysql://<user>:<password>@<host>:3306/<database>`

Current production state:

- Secret Manager placeholder `BALESHOP_DATABASE_URL` exists.
- No usable production secret version has been attached.
- Cloud Run cannot use `mysql://...@localhost:3306/bale_shop` because `localhost` would mean the Cloud Run container, not the DigitalOcean droplet.
- Cloud Run cannot use `134.209.182.39:3306` while MySQL is bound to `127.0.0.1`.

## Recommended Production Options

Option 1: Move Baleshop MySQL to a managed database.

- Recommended for production.
- Create a read-only DatabaseAgent user.
- Add `BALESHOP_DATABASE_URL` in Secret Manager.
- Attach the secret to Cloud Run.

Option 2: Expose MySQL securely from the droplet.

- Bind MySQL to a reachable private or public interface.
- Restrict firewall access.
- Create a read-only MySQL user for YenkasaCode Agent.
- Prefer static egress from Cloud Run before allowlisting.

Option 3: Add a read-only internal inventory endpoint to Baleshop API.

- Avoids exposing MySQL directly.
- DatabaseAgent would call the Baleshop API instead of MySQL.
- Requires Baleshop code changes and authentication.

Option 4: Use an SSH tunnel.

- Useful for local debugging.
- Not recommended for Cloud Run production runtime.

## Cloud SQL Preparation Before Pause

The migration was paused before any live application switch.

Completed before pause:

- Created a new separate Cloud SQL instance:
  - Instance name: `yenkasa-store-mysql`
  - Database engine: MySQL 8
  - Region: `europe-west1`
  - Status: `RUNNABLE`
  - Public IP: `34.78.8.96`
- Stored generated root password in Secret Manager:
  - `BALESHOP_CLOUDSQL_ROOT_PASSWORD`

Not done before pause:

- Did not migrate data.
- Did not create app/read-only users.
- Did not change Baleshop Spring Boot config.
- Did not affect live store signups.

Recommended next move:

- Keep the live Baleshop droplet using `localhost:3306/bale_shop` until a planned migration window.
- Use YenkasaCode Agent later to plan the Cloud SQL migration, create read-only/app users, import the dump, validate row counts, and switch the Spring Boot datasource only after successful validation.

## Safe Future Trace Commands

Run on the Baleshop droplet:

```bash
cd /root/triciabales
grep -RInE 'spring.datasource|jakarta.persistence.jdbc|jdbc:mysql|MYSQL|DB_|DATABASE' . --exclude-dir=target 2>/dev/null
ss -lntp | grep 3306 || true
mysql -u balesuser -p bale_shop
```

Inside MySQL:

```sql
SHOW DATABASES;
USE bale_shop;
SHOW TABLES;
SELECT table_name, table_rows
FROM information_schema.tables
WHERE table_schema = 'bale_shop'
ORDER BY table_name;
SHOW VARIABLES LIKE 'bind_address';
EXIT;
```

Schema-only dump from the shell, not from inside the MySQL prompt:

```bash
mysqldump -u balesuser -p --no-data bale_shop > /tmp/baleshop_schema.sql
head -n 120 /tmp/baleshop_schema.sql
```

## Security Notes

- The local Spring datasource password appeared in command output during manual discovery. Rotate the Baleshop MySQL password before treating this environment as production-safe.
- Prefer creating a dedicated read-only database user for YenkasaCode Agent.
- Do not store live SQL credentials in repo files.
