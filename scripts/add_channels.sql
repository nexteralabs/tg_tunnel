-- Channels table for Telegram Channel Gateway
CREATE TABLE IF NOT EXISTS channels (
    channel_id TEXT PRIMARY KEY,
    telegram_chat_id TEXT NOT NULL,
    bot_token TEXT NOT NULL,
    callback_url TEXT,  -- Nullable: PROMPT channels use per-prompt callbacks
    last_update_id BIGINT DEFAULT 0,
    is_active BOOLEAN DEFAULT true,
    registered_at TIMESTAMPTZ DEFAULT now(),
    channel_type TEXT DEFAULT 'MESSAGE'  -- 'MESSAGE' or 'PROMPT'
);

-- Migration for existing tables: Add channel_type if it doesn't exist
DO $$
BEGIN
    IF NOT EXISTS (
        SELECT 1 FROM information_schema.columns
        WHERE table_name = 'channels' AND column_name = 'channel_type'
    ) THEN
        ALTER TABLE channels ADD COLUMN channel_type TEXT DEFAULT 'MESSAGE';
    END IF;
END $$;

-- Migration: Make callback_url nullable (idempotent)
DO $$
BEGIN
    ALTER TABLE channels ALTER COLUMN callback_url DROP NOT NULL;
EXCEPTION
    WHEN undefined_column THEN NULL;
    WHEN others THEN NULL;
END $$;

-- Create indexes (safe to run multiple times)
CREATE INDEX IF NOT EXISTS idx_channels_active ON channels(is_active);
CREATE INDEX IF NOT EXISTS idx_channels_chat ON channels(telegram_chat_id);
CREATE INDEX IF NOT EXISTS idx_channels_type ON channels(channel_type);
