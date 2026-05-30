-- MyReps database schema.
-- Apply once against a fresh Postgres database. Idempotent re-runs are not supported;
-- this file is the source of truth for schema, not a migration history.

-- One row per on-demand research request (rep overview, election, or issue stance).
CREATE TABLE research_tasks (
    id                  text PRIMARY KEY,
    task_type           text NOT NULL DEFAULT 'rep',
    target              text NOT NULL,
    status              text NOT NULL DEFAULT 'done',
    model               text,
    input_tokens        int  NOT NULL DEFAULT 0,
    output_tokens       int  NOT NULL DEFAULT 0,
    input_cost_per_m    numeric(10, 4),
    output_cost_per_m   numeric(10, 4),
    search_tool         text,
    tool_calls          int  NOT NULL DEFAULT 0,
    cost_per_search     numeric(10, 6),
    environment         text,
    created_at          timestamptz NOT NULL DEFAULT now()
);

CREATE INDEX idx_research_tasks_created_at ON research_tasks (created_at);

-- Money ledger. LLM/search outflows written automatically; inflows are manual.
CREATE TABLE transactions (
    id                serial PRIMARY KEY,
    type              text NOT NULL CHECK (type IN ('inflow', 'outflow')),
    source            text NOT NULL,
    billing_model     text NOT NULL CHECK (billing_model IN ('per_request', 'bulk', 'subscription')),
    amount_usd        numeric(10, 4) NOT NULL,
    balance_after     numeric(10, 4),
    description       text,
    research_task_id  text REFERENCES research_tasks(id),
    created_at        timestamptz NOT NULL DEFAULT now()
);

CREATE INDEX idx_transactions_source          ON transactions (source);
CREATE INDEX idx_transactions_created_at      ON transactions (created_at);
CREATE INDEX idx_transactions_research_task_id ON transactions (research_task_id);

-- Political issues taxonomy for the "On the Issues" classifier.
-- The classifier LLM matches user input against active rows at request time.
CREATE TABLE issues (
    id          text PRIMARY KEY,
    label       text NOT NULL,
    active      boolean NOT NULL DEFAULT true,
    created_at  timestamptz NOT NULL DEFAULT now()
);

INSERT INTO issues (id, label) VALUES
    ('abortion', 'Abortion'),
    ('affordable_housing', 'Affordable Housing'),
    ('artificial_intelligence', 'Artificial Intelligence'),
    ('border_security', 'Border Security'),
    ('campaign_finance', 'Campaign Finance'),
    ('childcare', 'Childcare'),
    ('civil_rights', 'Civil Rights'),
    ('climate_change', 'Climate Change'),
    ('criminal_justice_reform', 'Criminal Justice Reform'),
    ('economy', 'Economy'),
    ('education', 'Education'),
    ('energy_policy', 'Energy Policy'),
    ('environment', 'Environment'),
    ('foreign_policy', 'Foreign Policy'),
    ('government_spending', 'Government Spending'),
    ('gun_control', 'Gun Control'),
    ('healthcare', 'Healthcare'),
    ('immigration', 'Immigration'),
    ('infrastructure', 'Infrastructure'),
    ('labor_rights', 'Labor Rights'),
    ('lgbtq_rights', 'LGBTQ+ Rights'),
    ('marijuana_legalization', 'Marijuana Legalization'),
    ('medicare', 'Medicare'),
    ('military_veterans', 'Military & Veterans'),
    ('minimum_wage', 'Minimum Wage'),
    ('national_security', 'National Security'),
    ('police_reform', 'Police Reform'),
    ('prescription_drug_costs', 'Prescription Drug Costs'),
    ('privacy_surveillance', 'Privacy & Surveillance'),
    ('public_transportation', 'Public Transportation'),
    ('racial_justice', 'Racial Justice'),
    ('social_security', 'Social Security'),
    ('student_debt', 'Student Debt'),
    ('supreme_court', 'Supreme Court'),
    ('tariffs_trade', 'Tariffs & Trade'),
    ('taxes', 'Taxes'),
    ('technology_regulation', 'Technology Regulation'),
    ('voting_rights', 'Voting Rights'),
    ('wage_inequality', 'Wage Inequality'),
    ('water_resources', 'Water Resources');

-- ---------------------------------------------------------------------------
-- Civics / America fun facts shown in the loading carousel while a rep's
-- AI overview is being researched. Reference data; edit rows directly.
-- ---------------------------------------------------------------------------
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
