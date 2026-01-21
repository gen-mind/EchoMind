-- PostgreSQL Initialization Script for EchoMind
-- Creates required databases for Authentik and API

-- Create Authentik database
CREATE DATABASE authentik;

-- Create EchoMind API database
CREATE DATABASE echomind;

-- Grant privileges (user already has superuser from POSTGRES_USER env var)
GRANT ALL PRIVILEGES ON DATABASE authentik TO postgres;
GRANT ALL PRIVILEGES ON DATABASE echomind TO postgres;
