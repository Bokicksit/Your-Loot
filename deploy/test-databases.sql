-- The single-user API in compose.test.yaml keeps its own database, so the
-- two stacks cannot see each other's accounts.
CREATE DATABASE solo OWNER getloot;
