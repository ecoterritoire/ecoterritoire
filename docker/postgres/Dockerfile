FROM postgis/postgis:16-3.4

COPY sql/script_postgres.sql /docker-entrypoint-initdb.d/01-schema.sql
COPY sql/seed_postgres.sql /docker-entrypoint-initdb.d/02-seed.sql
