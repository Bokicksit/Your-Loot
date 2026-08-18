-- The single-user API in compose.test.yaml keeps its own database, so the
-- two stacks cannot see each other's accounts.
CREATE DATABASE solo OWNER getloot;

-- And the open-signup API keeps a third, for the same reason plus one more:
-- each container runs migrations on start, and pointing two of them at one
-- database is a race nobody needs in a test suite.
CREATE DATABASE opensignup OWNER getloot;

-- And a fourth that is deliberately left empty. A whole-server restore is
-- only allowed into an install with nothing in it, and the only honest way
-- to test the path somebody rebuilds a machine with is to actually do it.
CREATE DATABASE freshinstall OWNER getloot;

-- A home server that shows its room off: single-user, profiles on. The
-- /loot page only exists in this combination, so it needs its own install —
-- api-single keeps profiles off to prove the default's absence.
CREATE DATABASE home OWNER getloot;
