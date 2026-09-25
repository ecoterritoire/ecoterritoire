CREATE EXTENSION IF NOT EXISTS postgis;

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