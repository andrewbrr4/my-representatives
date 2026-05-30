-- One-off migration: add the facts table + seed to an already-provisioned DB.
-- schema.sql is apply-once for fresh databases; run this against dev/prod.
CREATE TABLE facts (
    id          SERIAL PRIMARY KEY,
    text        TEXT NOT NULL,
    active      BOOLEAN NOT NULL DEFAULT TRUE,
    created_at  TIMESTAMPTZ NOT NULL DEFAULT now()
);

INSERT INTO facts (text) VALUES
  ('The U.S. Constitution is the oldest written national constitution still in use, ratified in 1788.'),
  ('The House of Representatives has 435 voting members, a number fixed by law since 1929.'),
  ('Each U.S. state gets exactly two senators, regardless of population — so Wyoming and California have equal Senate representation.'),
  ('A senator serves a six-year term; a House representative serves a two-year term.'),
  ('It takes a two-thirds vote of both chambers of Congress to override a presidential veto.'),
  ('The Bill of Rights is the name for the first ten amendments to the Constitution, ratified in 1791.'),
  ('Washington, D.C. residents could not vote for president until the 23rd Amendment was ratified in 1961.'),
  ('The Speaker of the House is second in the line of presidential succession, after the vice president.'),
  ('Congress has the sole power to declare war, though it has formally done so only 11 times.'),
  ('The 26th Amendment lowered the voting age from 21 to 18 in 1971.'),
  ('There are 50 stars on the American flag for the states and 13 stripes for the original colonies.'),
  ('A filibuster in the Senate can be ended by a "cloture" vote, which today generally requires 60 senators.'),
  ('The first Congress in 1789 had just 26 senators and 65 representatives.'),
  ('Federal judges, including Supreme Court justices, are appointed for life and serve "during good behavior."'),
  ('Only the House can introduce bills that raise revenue, per the Constitution''s Origination Clause.'),
  ('The presidential term limit of two terms was set by the 22nd Amendment, ratified in 1951.'),
  ('Voter turnout in U.S. presidential elections is typically higher than in midterm congressional elections.'),
  ('The word "gerrymander" dates to 1812, named for Massachusetts Governor Elbridge Gerry and a salamander-shaped district.');
