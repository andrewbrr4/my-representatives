-- 001: Create jobs and transactions tables

CREATE TABLE IF NOT EXISTS jobs (
    id              text PRIMARY KEY,
    address         text NOT NULL,
    reps_found      int NOT NULL DEFAULT 0,
    reps_researched int NOT NULL DEFAULT 0,
    reps_cached     int NOT NULL DEFAULT 0,
    input_tokens    int NOT NULL DEFAULT 0,
    output_tokens   int NOT NULL DEFAULT 0,
    tool_calls      int NOT NULL DEFAULT 0,
    status          text NOT NULL DEFAULT 'done',
    created_at      timestamptz NOT NULL DEFAULT now()
);

CREATE TABLE IF NOT EXISTS transactions (
    id              serial PRIMARY KEY,
    type            text NOT NULL CHECK (type IN ('inflow', 'outflow')),
    source          text NOT NULL,
    billing_model   text NOT NULL CHECK (billing_model IN ('per_request', 'bulk', 'subscription')),
    amount_usd      numeric(10, 4) NOT NULL,
    description     text,
    job_id          text REFERENCES jobs(id),
    created_at      timestamptz NOT NULL DEFAULT now(),
    balance_after   numeric(10, 4)
);

CREATE INDEX IF NOT EXISTS idx_transactions_source ON transactions(source);
CREATE INDEX IF NOT EXISTS idx_transactions_created_at ON transactions(created_at);
CREATE INDEX IF NOT EXISTS idx_transactions_job_id ON transactions(job_id);
CREATE INDEX IF NOT EXISTS idx_jobs_created_at ON jobs(created_at);
