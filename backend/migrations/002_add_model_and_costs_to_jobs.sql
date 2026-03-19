-- 002: Add model, per-token costs, and search tool/cost to jobs
-- Captures pricing at request time so historical cost analysis survives rate changes.

ALTER TABLE jobs ADD COLUMN IF NOT EXISTS model              text;
ALTER TABLE jobs ADD COLUMN IF NOT EXISTS input_cost_per_m   numeric(10, 4);
ALTER TABLE jobs ADD COLUMN IF NOT EXISTS output_cost_per_m  numeric(10, 4);
ALTER TABLE jobs ADD COLUMN IF NOT EXISTS search_tool        text;
ALTER TABLE jobs ADD COLUMN IF NOT EXISTS cost_per_search    numeric(10, 6);
ALTER TABLE jobs ADD COLUMN IF NOT EXISTS environment        text;
