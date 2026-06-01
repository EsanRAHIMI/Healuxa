-- Per-service logical databases (Phase 0). TechSpec §7.3 — identity isolated first.
CREATE DATABASE identity;
-- Dev/test isolation: same schema/migrations, separate data from laptop development.
CREATE DATABASE identity_test;
