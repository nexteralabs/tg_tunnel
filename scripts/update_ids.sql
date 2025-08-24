-- Migration to simple counter-based IDs
-- This will be run as a one-time migration

BEGIN;

-- Add new auto-incrementing ID column
ALTER TABLE prompts ADD COLUMN prompt_num SERIAL;

-- Update prompt_options to reference the new ID format
-- For now we'll keep both old and new formats during transition

-- Add index for the new prompt_num
CREATE INDEX idx_prompts_prompt_num ON prompts(prompt_num);

COMMIT;