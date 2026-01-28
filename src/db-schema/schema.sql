-- EchoMind Database Schema
-- Single-tenant architecture with per-user/group/org vector collections
-- PostgreSQL 15+

-- ============================================================================
-- USERS & GROUPS
-- ============================================================================

-- Users table (synced from Authentik OIDC)
CREATE TABLE users (
    id SERIAL PRIMARY KEY,
    user_name VARCHAR(255) NOT NULL UNIQUE,
    email VARCHAR(255) NOT NULL UNIQUE,
    first_name VARCHAR(255),
    last_name VARCHAR(255),
    external_id TEXT,                           -- Authentik user ID
    roles TEXT[] NOT NULL DEFAULT '{}',         -- ['user', 'admin']
    groups TEXT[] NOT NULL DEFAULT '{}',        -- ['engineering', 'sales']
    preferences JSONB NOT NULL DEFAULT '{}',    -- User preferences (theme, default_assistant_id, etc.)
    is_active BOOLEAN NOT NULL DEFAULT TRUE,
    creation_date TIMESTAMP NOT NULL DEFAULT NOW(),
    last_update TIMESTAMP,
    user_id_last_update INTEGER REFERENCES users(id),
    last_login TIMESTAMP
);

CREATE INDEX idx_users_email ON users(email);
CREATE INDEX idx_users_external_id ON users(external_id);

-- ============================================================================
-- LLM & EMBEDDING MODELS
-- ============================================================================

-- LLM configurations (TGI, vLLM, OpenAI, Anthropic, etc.)
CREATE TABLE llms (
    id SMALLSERIAL PRIMARY KEY,
    name VARCHAR(255) NOT NULL,
    provider VARCHAR(50) NOT NULL,              -- 'tgi', 'vllm', 'openai', 'anthropic', 'ollama'
    model_id VARCHAR(255) NOT NULL,             -- e.g., 'mistralai/Mistral-7B-Instruct-v0.2'
    endpoint VARCHAR NOT NULL,                  -- e.g., 'http://inference:8080'
    api_key VARCHAR,                            -- Encrypted, nullable for local models
    max_tokens INTEGER DEFAULT 4096,
    temperature NUMERIC(3,2) DEFAULT 0.7,
    is_default BOOLEAN NOT NULL DEFAULT FALSE,
    is_active BOOLEAN NOT NULL DEFAULT TRUE,
    creation_date TIMESTAMP NOT NULL DEFAULT NOW(),
    last_update TIMESTAMP,
    user_id_last_update INTEGER REFERENCES users(id),
    deleted_date TIMESTAMP
);

-- Embedding model configurations (cluster-wide)
CREATE TABLE embedding_models (
    id SMALLSERIAL PRIMARY KEY,
    model_id VARCHAR NOT NULL,                  -- e.g., 'nvidia/llama-nemotron-embed-1b-v2'
    model_name VARCHAR NOT NULL,                -- Display name
    model_dimension INTEGER NOT NULL,           -- e.g., 768
    endpoint VARCHAR,                           -- Optional: external embedding service URL
    is_active BOOLEAN NOT NULL DEFAULT FALSE,   -- Only one can be active at a time
    creation_date TIMESTAMP NOT NULL DEFAULT NOW(),
    last_update TIMESTAMP,
    user_id_last_update INTEGER REFERENCES users(id),
    deleted_date TIMESTAMP
);

-- Ensure only one active embedding model
CREATE UNIQUE INDEX idx_embedding_models_active ON embedding_models(is_active) WHERE is_active = TRUE;

-- ============================================================================
-- ASSISTANTS
-- ============================================================================

-- AI assistant configurations with custom prompts
CREATE TABLE assistants (
    id SMALLSERIAL PRIMARY KEY,
    name VARCHAR(255) NOT NULL,
    description TEXT NOT NULL,
    llm_id SMALLINT REFERENCES llms(id),
    system_prompt TEXT NOT NULL,                -- System prompt for the LLM
    task_prompt TEXT NOT NULL,                  -- Task prompt template with {context} and {query} placeholders
    starter_messages JSONB NOT NULL DEFAULT '[]', -- Suggested conversation starters
    is_default BOOLEAN NOT NULL DEFAULT FALSE,
    is_visible BOOLEAN NOT NULL DEFAULT TRUE,
    display_priority INTEGER DEFAULT 0,
    created_by INTEGER REFERENCES users(id),
    creation_date TIMESTAMP NOT NULL DEFAULT NOW(),
    last_update TIMESTAMP,
    user_id_last_update INTEGER REFERENCES users(id),
    deleted_date TIMESTAMP
);

CREATE INDEX idx_assistants_is_visible ON assistants(is_visible) WHERE deleted_date IS NULL;

-- ============================================================================
-- CONNECTORS & DOCUMENTS
-- ============================================================================

-- Data source connectors (Teams, Google Drive, etc.)
CREATE TABLE connectors (
    id SMALLSERIAL PRIMARY KEY,
    name VARCHAR(255) NOT NULL,
    type VARCHAR(50) NOT NULL,                  -- 'teams', 'google_drive', 'onedrive', 'web', 'file'
    config JSONB NOT NULL,                      -- Connector-specific configuration
    state JSONB NOT NULL DEFAULT '{}',          -- Sync state (cursors, tokens, etc.)
    refresh_freq_minutes INTEGER,               -- Auto-refresh interval (null = manual only)
    user_id INTEGER NOT NULL REFERENCES users(id), -- Owner
    scope VARCHAR(20) NOT NULL DEFAULT 'user',  -- 'user', 'group', 'org' - determines vector collection
    scope_id TEXT,                              -- Group name if scope='group', null for user/org
    status VARCHAR(50) NOT NULL DEFAULT 'pending', -- 'pending', 'syncing', 'active', 'error', 'disabled'
    status_message TEXT,                        -- Error message or status details
    last_sync_at TIMESTAMP,
    docs_analyzed BIGINT NOT NULL DEFAULT 0,
    creation_date TIMESTAMP NOT NULL DEFAULT NOW(),
    last_update TIMESTAMP,
    user_id_last_update INTEGER REFERENCES users(id),
    deleted_date TIMESTAMP
);

CREATE INDEX idx_connectors_user_id ON connectors(user_id);
CREATE INDEX idx_connectors_status ON connectors(status) WHERE deleted_date IS NULL;

-- Documents ingested from connectors
CREATE TABLE documents (
    id BIGSERIAL PRIMARY KEY,
    parent_id BIGINT REFERENCES documents(id),  -- For hierarchical documents (folders, threads)
    connector_id SMALLINT NOT NULL REFERENCES connectors(id),
    source_id TEXT NOT NULL,                    -- Unique ID from source system
    url TEXT,                                   -- Source URL or MinIO path (minio:bucket:file)
    original_url TEXT,                          -- Original URL before any transformations
    title TEXT,                                 -- Document title/name
    content_type VARCHAR(100),                  -- MIME type
    signature TEXT,                             -- Hash for change detection
    chunking_session UUID,                      -- Groups chunks from same processing run
    status VARCHAR(50) NOT NULL DEFAULT 'pending', -- 'pending', 'processing', 'completed', 'failed'
    status_message TEXT,                        -- Error message if failed
    chunk_count INTEGER DEFAULT 0,              -- Number of chunks created
    creation_date TIMESTAMP NOT NULL DEFAULT NOW(),
    last_update TIMESTAMP,
    user_id_last_update INTEGER REFERENCES users(id)
);

CREATE INDEX idx_documents_connector_id ON documents(connector_id);
CREATE INDEX idx_documents_status ON documents(status);
CREATE INDEX idx_documents_source_id ON documents(connector_id, source_id);

-- ============================================================================
-- CHAT SESSIONS & MESSAGES
-- ============================================================================

-- Chat sessions
CREATE TABLE chat_sessions (
    id SERIAL PRIMARY KEY,
    user_id INTEGER NOT NULL REFERENCES users(id),
    assistant_id SMALLINT NOT NULL REFERENCES assistants(id),
    title TEXT NOT NULL DEFAULT 'New Chat',
    mode VARCHAR(20) NOT NULL DEFAULT 'chat',   -- 'chat', 'one_shot'
    message_count INTEGER NOT NULL DEFAULT 0,
    creation_date TIMESTAMP NOT NULL DEFAULT NOW(),
    last_update TIMESTAMP,
    user_id_last_update INTEGER REFERENCES users(id),
    last_message_at TIMESTAMP,
    deleted_date TIMESTAMP
);

CREATE INDEX idx_chat_sessions_user_id ON chat_sessions(user_id) WHERE deleted_date IS NULL;

-- Chat messages
CREATE TABLE chat_messages (
    id BIGSERIAL PRIMARY KEY,
    chat_session_id INTEGER NOT NULL REFERENCES chat_sessions(id) ON DELETE CASCADE,
    role VARCHAR(20) NOT NULL,                  -- 'user', 'assistant', 'system'
    content TEXT NOT NULL,
    token_count INTEGER NOT NULL DEFAULT 0,
    parent_message_id BIGINT REFERENCES chat_messages(id),  -- For branching conversations
    rephrased_query TEXT,                       -- Agent's rephrased query for retrieval
    retrieval_context JSONB,                    -- Retrieved chunks used for this response
    tool_calls JSONB,                           -- Tools invoked during response generation
    error TEXT,                                 -- Error message if generation failed
    creation_date TIMESTAMP NOT NULL DEFAULT NOW(),
    last_update TIMESTAMP,
    user_id_last_update INTEGER REFERENCES users(id)
);

CREATE INDEX idx_chat_messages_session_id ON chat_messages(chat_session_id);

-- Message feedback (thumbs up/down)
CREATE TABLE chat_message_feedbacks (
    id SERIAL PRIMARY KEY,
    chat_message_id BIGINT NOT NULL REFERENCES chat_messages(id) ON DELETE CASCADE,
    user_id INTEGER NOT NULL REFERENCES users(id),
    is_positive BOOLEAN NOT NULL,               -- true = thumbs up, false = thumbs down
    feedback_text TEXT,                         -- Optional text feedback
    creation_date TIMESTAMP NOT NULL DEFAULT NOW(),
    last_update TIMESTAMP,
    user_id_last_update INTEGER REFERENCES users(id),
    UNIQUE(chat_message_id, user_id)
);

-- Documents referenced in chat messages (for citations)
CREATE TABLE chat_message_documents (
    id BIGSERIAL PRIMARY KEY,
    chat_message_id BIGINT NOT NULL REFERENCES chat_messages(id) ON DELETE CASCADE,
    document_id BIGINT NOT NULL REFERENCES documents(id) ON DELETE CASCADE,
    chunk_id TEXT,                              -- Specific chunk ID from Qdrant
    relevance_score NUMERIC(5,4),               -- Retrieval score
    creation_date TIMESTAMP NOT NULL DEFAULT NOW(),
    last_update TIMESTAMP,
    user_id_last_update INTEGER REFERENCES users(id),
    UNIQUE(chat_message_id, document_id, chunk_id)
);

CREATE INDEX idx_chat_message_documents_message_id ON chat_message_documents(chat_message_id);

-- ============================================================================
-- AGENT MEMORY
-- ============================================================================

-- Long-term episodic memory (past interactions worth remembering)
CREATE TABLE agent_memories (
    id SERIAL PRIMARY KEY,
    user_id INTEGER NOT NULL REFERENCES users(id),
    memory_type VARCHAR(50) NOT NULL,           -- 'episodic', 'semantic', 'procedural'
    content TEXT NOT NULL,                      -- The memory content
    embedding_id TEXT,                          -- Reference to vector in Qdrant
    importance_score NUMERIC(3,2) DEFAULT 0.5,  -- How important is this memory (0-1)
    access_count INTEGER NOT NULL DEFAULT 0,    -- Times this memory was retrieved
    last_accessed_at TIMESTAMP,
    source_session_id INTEGER REFERENCES chat_sessions(id),
    creation_date TIMESTAMP NOT NULL DEFAULT NOW(),
    last_update TIMESTAMP,
    user_id_last_update INTEGER REFERENCES users(id),
    expires_at TIMESTAMP                        -- Optional expiration
);

CREATE INDEX idx_agent_memories_user_id ON agent_memories(user_id);
CREATE INDEX idx_agent_memories_type ON agent_memories(memory_type);

-- ============================================================================
-- FUNCTIONS & TRIGGERS
-- ============================================================================

-- Function to update last_update timestamp
CREATE OR REPLACE FUNCTION update_last_update_column()
RETURNS TRIGGER AS $$
BEGIN
    NEW.last_update = NOW();
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

-- Apply last_update trigger to relevant tables
CREATE TRIGGER update_users_last_update BEFORE UPDATE ON users
    FOR EACH ROW EXECUTE FUNCTION update_last_update_column();

CREATE TRIGGER update_llms_last_update BEFORE UPDATE ON llms
    FOR EACH ROW EXECUTE FUNCTION update_last_update_column();

CREATE TRIGGER update_embedding_models_last_update BEFORE UPDATE ON embedding_models
    FOR EACH ROW EXECUTE FUNCTION update_last_update_column();

CREATE TRIGGER update_assistants_last_update BEFORE UPDATE ON assistants
    FOR EACH ROW EXECUTE FUNCTION update_last_update_column();

CREATE TRIGGER update_connectors_last_update BEFORE UPDATE ON connectors
    FOR EACH ROW EXECUTE FUNCTION update_last_update_column();

CREATE TRIGGER update_documents_last_update BEFORE UPDATE ON documents
    FOR EACH ROW EXECUTE FUNCTION update_last_update_column();

CREATE TRIGGER update_chat_sessions_last_update BEFORE UPDATE ON chat_sessions
    FOR EACH ROW EXECUTE FUNCTION update_last_update_column();

CREATE TRIGGER update_chat_messages_last_update BEFORE UPDATE ON chat_messages
    FOR EACH ROW EXECUTE FUNCTION update_last_update_column();

CREATE TRIGGER update_chat_message_feedbacks_last_update BEFORE UPDATE ON chat_message_feedbacks
    FOR EACH ROW EXECUTE FUNCTION update_last_update_column();

CREATE TRIGGER update_chat_message_documents_last_update BEFORE UPDATE ON chat_message_documents
    FOR EACH ROW EXECUTE FUNCTION update_last_update_column();

CREATE TRIGGER update_agent_memories_last_update BEFORE UPDATE ON agent_memories
    FOR EACH ROW EXECUTE FUNCTION update_last_update_column();

-- Function to update chat session message count
CREATE OR REPLACE FUNCTION update_chat_session_message_count()
RETURNS TRIGGER AS $$
BEGIN
    IF TG_OP = 'INSERT' THEN
        UPDATE chat_sessions 
        SET message_count = message_count + 1,
            last_message_at = NOW()
        WHERE id = NEW.chat_session_id;
    ELSIF TG_OP = 'DELETE' THEN
        UPDATE chat_sessions 
        SET message_count = message_count - 1
        WHERE id = OLD.chat_session_id;
    END IF;
    RETURN NULL;
END;
$$ LANGUAGE plpgsql;

CREATE TRIGGER update_chat_session_stats AFTER INSERT OR DELETE ON chat_messages
    FOR EACH ROW EXECUTE FUNCTION update_chat_session_message_count();
