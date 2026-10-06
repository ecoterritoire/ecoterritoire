CREATE EXTENSION IF NOT EXISTS postgis;

CREATE TABLE IF NOT EXISTS "app_users" (
	"id" bigserial PRIMARY KEY,
	"username" varchar(128) NOT NULL UNIQUE,
	"password_hash" varchar(255) NOT NULL,
	"role" varchar(32) NOT NULL DEFAULT 'admin',
	"created_at" timestamptz NOT NULL DEFAULT now(),
	"last_login_at" timestamptz,
	"is_active" boolean NOT NULL DEFAULT true
);

CREATE TABLE IF NOT EXISTS "api_tokens" (
	"id" bigserial PRIMARY KEY,
	"token_hash" varchar(64) NOT NULL UNIQUE,
	"description" varchar(255) NOT NULL DEFAULT '',
	"created_at" timestamptz NOT NULL DEFAULT now(),
	"last_used_at" timestamptz,
	"is_active" boolean NOT NULL DEFAULT true,
	"user_id" bigint REFERENCES "app_users"("id"),
	"usage_count" bigint NOT NULL DEFAULT 0
);

ALTER TABLE "api_tokens"
	ADD COLUMN IF NOT EXISTS "user_id" bigint REFERENCES "app_users"("id");
ALTER TABLE "api_tokens"
	ADD COLUMN IF NOT EXISTS "usage_count" bigint NOT NULL DEFAULT 0;

CREATE INDEX IF NOT EXISTS api_tokens_active_hash_idx
	ON "api_tokens" ("token_hash")
	WHERE "is_active" = true;

CREATE TABLE IF NOT EXISTS "admin_sessions" (
	"id" bigserial PRIMARY KEY,
	"user_id" bigint NOT NULL REFERENCES "app_users"("id") ON DELETE CASCADE,
	"token_hash" varchar(64) NOT NULL UNIQUE,
	"created_at" timestamptz NOT NULL DEFAULT now(),
	"last_used_at" timestamptz,
	"expires_at" timestamptz NOT NULL,
	"is_active" boolean NOT NULL DEFAULT true
);

CREATE INDEX IF NOT EXISTS admin_sessions_active_hash_idx
	ON "admin_sessions" ("token_hash")
	WHERE "is_active" = true;

CREATE TABLE IF NOT EXISTS "departements" (
	"code_dpt" varchar(3) NOT NULL UNIQUE,
	"nom" varchar(255) NOT NULL,
	PRIMARY KEY ("code_dpt")
);

CREATE TABLE IF NOT EXISTS "communes" (
	"code_insee" varchar(5) NOT NULL UNIQUE,
	"nom" varchar(255) NOT NULL,
	"code_dpt" varchar(3) NOT NULL,
	PRIMARY KEY ("code_insee")
);

DO $$
BEGIN
	IF NOT EXISTS (
		SELECT 1
		FROM pg_constraint
		WHERE conname = 'communes_fk2'
	) THEN
		ALTER TABLE "communes"
			ADD CONSTRAINT "communes_fk2"
			FOREIGN KEY ("code_dpt") REFERENCES "departements"("code_dpt");
	END IF;
END $$;

CREATE TABLE IF NOT EXISTS "stations" (
	"code_site" varchar(32) PRIMARY KEY,
	"nom_site" varchar(255) NOT NULL,
	"organisme" varchar(255),
	"code_zas" varchar(32),
	"zas" varchar(255),
	"type_implantation" varchar(100),
	"code_insee" varchar(5),
	"code_dpt" varchar(3),
	"latitude" double precision,
	"longitude" double precision,
	"position" geometry(Point, 4326),
	"updated_at" timestamptz NOT NULL DEFAULT now(),
	CONSTRAINT stations_commune_fk
		FOREIGN KEY ("code_insee") REFERENCES "communes"("code_insee"),
	CONSTRAINT stations_departement_fk
		FOREIGN KEY ("code_dpt") REFERENCES "departements"("code_dpt"),
	CONSTRAINT stations_position_pair_ck
		CHECK (("latitude" IS NULL AND "longitude" IS NULL)
			OR ("latitude" BETWEEN -90 AND 90 AND "longitude" BETWEEN -180 AND 180))
);

CREATE INDEX IF NOT EXISTS stations_code_insee_idx ON "stations" ("code_insee");
CREATE INDEX IF NOT EXISTS stations_code_dpt_idx ON "stations" ("code_dpt");
CREATE INDEX IF NOT EXISTS stations_position_idx ON "stations" USING GIST ("position");
