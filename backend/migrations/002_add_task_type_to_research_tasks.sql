-- 002: Add task_type column to research_tasks for distinguishing rep vs election research.
ALTER TABLE research_tasks ADD COLUMN task_type text NOT NULL DEFAULT 'rep';
