-- 002: Add task_type column and rename representative → target.
-- task_type: "rep" or "election" to distinguish research types.
-- target: generic label for what was researched (rep name or election identifier).

ALTER TABLE research_tasks ADD COLUMN task_type text NOT NULL DEFAULT 'rep';
ALTER TABLE research_tasks RENAME COLUMN representative TO target;
