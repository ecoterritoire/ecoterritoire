CREATE TABLE IF NOT EXISTS "communes" (
	"code_insee" varchar(5) NOT NULL UNIQUE,
	"nom" varchar(255) NOT NULL,
	"code_dpt" varchar(2) NOT NULL,
	PRIMARY KEY ("code_insee")
);
CREATE TABLE IF NOT EXISTS "departements" (
	"code_dpt" varchar(2) NOT NULL UNIQUE,
	"nom" varchar(255) NOT NULL,
	PRIMARY KEY ("code_dpt")
);
CREATE TABLE IF NOT EXISTS "token" (
	"id" serial NOT NULL UNIQUE,
	"name" varchar(45) NOT NULL,
	"hash_token" varchar(60) NOT NULL UNIQUE,
	"created_at" date NOT NULL,
	PRIMARY KEY ("id")
);
ALTER TABLE "communes" ADD CONSTRAINT "communes_fk2" FOREIGN KEY ("code_dpt") REFERENCES "departements"("code_dpt");