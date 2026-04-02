-- 003_create_issues_table.sql
-- Political issues taxonomy for "On the Issues" feature.
-- The classifier LLM matches user input against these rows at request time.

CREATE TABLE IF NOT EXISTS issues (
    id TEXT PRIMARY KEY,
    label TEXT NOT NULL,
    active BOOLEAN NOT NULL DEFAULT TRUE,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

-- Seed initial taxonomy
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
    ('water_resources', 'Water Resources')
ON CONFLICT (id) DO NOTHING;
