#!/bin/bash
# Fix Langfuse certificate issue
# Recreates containers with healthcheck fix and verifies certificate

set -e
cd /root/echo-mind/deployment/docker-cluster

echo "========================================="
echo "LANGFUSE CERTIFICATE FIX"
echo "========================================="
echo ""

if [ -f .env ]; then
    echo "✅ Loading .env..."
    set -a
    source .env
    set +a
else
    echo "❌ .env not found!"
    exit 1
fi

echo "1️⃣ Git state:"
git log -1 --oneline

echo ""
echo "2️⃣ Verifying healthcheck fix:"
if grep -q "0.0.0.0:3000" docker-compose-langfuse.yml; then
    echo "✅ Healthcheck uses 0.0.0.0"
else
    echo "❌ Still uses localhost!"
    exit 1
fi

echo ""
echo "3️⃣ Stopping containers..."
docker compose \
    -f docker-compose.yml \
    -f docker-compose-observability.yml \
    -f docker-compose-langfuse.yml \
    -f docker-compose-host.yml \
    -f docker-compose-observability-host.yml \
    -f docker-compose-langfuse-host.yml \
    --profile observability \
    --profile langfuse \
    --env-file .env \
    down

echo ""
echo "4️⃣ Starting cluster..."
./cluster.sh -H start

echo ""
echo "5️⃣ Waiting 70 seconds for healthcheck..."
for i in {70..1}; do
    printf "\r⏳ %2d seconds remaining..." $i
    sleep 1
done
echo ""

echo ""
echo "6️⃣ Container health:"
docker ps --filter "name=langfuse" --format "table {{.Names}}\t{{.Status}}"

echo ""
echo "7️⃣ Traefik router:"
ROUTER=$(docker exec infra-traefik wget -qO- http://localhost:8080/api/http/routers 2>/dev/null | jq '.[] | select(.name | contains("langfuse"))')
if [ -n "$ROUTER" ]; then
    echo "✅ Traefik HAS langfuse router"
    echo "$ROUTER" | jq '{name, entryPoints, tls}'
else
    echo "❌ No router found (container unhealthy?)"
fi

echo ""
echo "8️⃣ Certificate check:"
ISSUER=$(curl -vI https://langfuse.demo.echomind.ch 2>&1 | grep -i issuer || echo "Connection failed")
echo "$ISSUER"

if echo "$ISSUER" | grep -qi "Let's Encrypt"; then
    echo ""
    echo "========================================="
    echo "🎉 SUCCESS! Certificate working!"
    echo "========================================="
elif echo "$ISSUER" | grep -qi "TRAEFIK DEFAULT"; then
    echo ""
    echo "⚠️  Still default cert. Monitor logs:"
    echo "docker logs infra-traefik -f | grep -i langfuse"
else
    echo ""
    echo "⚠️  Could not determine certificate status"
fi

echo ""
echo "DONE"
