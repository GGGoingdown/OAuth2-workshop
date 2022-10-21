-- upgrade --
CREATE TABLE IF NOT EXISTS "users" (
    "id" SERIAL NOT NULL PRIMARY KEY,
    "name" VARCHAR(50) NOT NULL,
    "email" VARCHAR(128)  UNIQUE,
    "password_hash" VARCHAR(128),
    "create_at" TIMESTAMPTZ NOT NULL,
    "last_login_at" TIMESTAMPTZ
);
CREATE INDEX IF NOT EXISTS "idx_users_email_133a6f" ON "users" ("email");
CREATE TABLE IF NOT EXISTS "line_login" (
    "update_at" TIMESTAMPTZ,
    "access_token" VARCHAR(300) NOT NULL,
    "refresh_token" VARCHAR(300) NOT NULL,
    "expires_in" TIMESTAMPTZ NOT NULL,
    "sub" VARCHAR(200) NOT NULL,
    "name" VARCHAR(50) NOT NULL,
    "picture" VARCHAR(200) NOT NULL,
    "email" VARCHAR(128),
    "user_id" INT NOT NULL  PRIMARY KEY REFERENCES "users" ("id") ON DELETE CASCADE
);
CREATE INDEX IF NOT EXISTS "idx_line_login_sub_564678" ON "line_login" ("sub");
COMMENT ON COLUMN "line_login"."sub" IS 'User ID for which the ID token is generated';
CREATE TABLE IF NOT EXISTS "line_notify" (
    "create_at" TIMESTAMPTZ NOT NULL,
    "update_at" TIMESTAMPTZ,
    "access_token" VARCHAR(300) NOT NULL,
    "is_revoked" BOOL NOT NULL  DEFAULT False,
    "user_id" INT NOT NULL  PRIMARY KEY REFERENCES "users" ("id") ON DELETE CASCADE
);
CREATE TABLE IF NOT EXISTS "line_notify_records" (
    "id" SERIAL NOT NULL PRIMARY KEY,
    "create_at" TIMESTAMPTZ NOT NULL,
    "message" TEXT NOT NULL,
    "image_thumb_nil" TEXT,
    "image_full_size" TEXT,
    "user_id" INT NOT NULL REFERENCES "users" ("id") ON DELETE CASCADE
);
CREATE INDEX IF NOT EXISTS "idx_line_notify_create__dcd478" ON "line_notify_records" ("create_at");
CREATE TABLE IF NOT EXISTS "aerich" (
    "id" SERIAL NOT NULL PRIMARY KEY,
    "version" VARCHAR(255) NOT NULL,
    "app" VARCHAR(100) NOT NULL,
    "content" JSONB NOT NULL
);
