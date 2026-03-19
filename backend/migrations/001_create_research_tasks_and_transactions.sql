-- 001: Create research_tasks and transactions tables
-- research_tasks tracks individual on-demand per-rep research requests.

DROP TABLE IF EXISTS transactions CASCADE;
DROP TABLE IF EXISTS research_tasks CASCADE;
DROP TABLE IF EXISTS jobs CASCADE;

CREATE TABLE research_tasks (
    id              text PRIMARY KEY,
    representative  text NOT NULL,
    input_tokens    int NOT NULL DEFAULT 0,
    output_tokens   int NOT NULL DEFAULT 0,
    tool_calls      int NOT NULL DEFAULT 0,
    status          text NOT NULL DEFAULT 'done',
    model           text,
    input_cost_per_m   numeric(10, 4),
    output_cost_per_m  numeric(10, 4),
    search_tool     text,
    cost_per_search numeric(10, 6),
    environment     text,
    created_at      timestamptz NOT NULL DEFAULT now()
);

CREATE TABLE transactions (
    id                serial PRIMARY KEY,
    type              text NOT NULL CHECK (type IN ('inflow', 'outflow')),
    source            text NOT NULL,
    billing_model     text NOT NULL CHECK (billing_model IN ('per_request', 'bulk', 'subscription')),
    amount_usd        numeric(10, 4) NOT NULL,
    description       text,
    research_task_id  text REFERENCES research_tasks(id),
    created_at        timestamptz NOT NULL DEFAULT now(),
    balance_after     numeric(10, 4)
);

CREATE INDEX idx_research_tasks_created_at ON research_tasks(created_at);
CREATE INDEX idx_transactions_source ON transactions(source);
CREATE INDEX idx_transactions_created_at ON transactions(created_at);
CREATE INDEX idx_transactions_research_task_id ON transactions(research_task_id);
