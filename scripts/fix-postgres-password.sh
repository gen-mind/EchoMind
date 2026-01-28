#!/bin/bash
# Fix PostgreSQL password mismatch
#
# USE THIS WHEN: You see "password authentication failed for user echomind"
# in postgres logs, but your .env file has the correct password.
#
# ROOT CAUSE: POSTGRES_PASSWORD env var only works on FIRST initialization.
# If the volume already has data, changing the env var does nothing.
# You must sync the password inside postgres to match.
#
# USAGE: Run from project root:
#   ./scripts/fix-postgres-password.sh

set -e

# Get the project root directory (parent of scripts/)
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"
CLUSTER_DIR="$PROJECT_ROOT/deployment/docker-cluster"

# Change to cluster directory where docker-compose.yml and .env are
cd "$CLUSTER_DIR"

# Source the .env file to get POSTGRES_USER and POSTGRES_PASSWORD
if [ ! -f ".env" ]; then
    echo "Error: .env file not found in $CLUSTER_DIR"
    echo "Copy .env.example to .env and configure it first."
    exit 1
fi

source .env

echo "Syncing postgres password to match .env file..."
echo "User: $POSTGRES_USER"

# Run ALTER ROLE inside the postgres container
docker compose exec postgres psql -U "$POSTGRES_USER" -d postgres -c "ALTER ROLE $POSTGRES_USER WITH PASSWORD '$POSTGRES_PASSWORD';"

echo "Password synced. Recreating services that connect to postgres..."

# Stop and start services (--force-recreate alone doesn't always work)
docker compose stop api authentik-server authentik-worker
docker compose up -d api authentik-server authentik-worker

echo "Done! All services should now connect successfully."
echo ""
echo "Verify with: docker compose logs api --tail 10"
