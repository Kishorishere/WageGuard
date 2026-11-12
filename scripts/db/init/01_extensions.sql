-- Run at first container start by the pgvector image's entrypoint.
-- Keeps extension enablement out of the application role's path.
CREATE EXTENSION IF NOT EXISTS vector;
