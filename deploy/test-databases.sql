-- The single-user API in compose.test.yaml keeps its own database, so the
-- two stacks cannot see each other's accounts.
CREATE DATABASE solo OWNER getloot;

-- And the open-signup API keeps a third, for the same reason plus one more:
-- each container runs migrations on start, and pointing two of them at one
-- database is a race nobody needs in a test suite.
CREATE DATABASE opensignup OWNER getloot;
