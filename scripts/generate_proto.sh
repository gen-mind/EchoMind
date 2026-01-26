#!/bin/bash
# Proto Generation Script for EchoMind
# Generates Python protobuf stubs, Pydantic models, and TypeScript types from .proto files
#
# Structure (per CLAUDE.md):
#   src/proto/public/*.proto   -> models/public/       (API-facing models)
#   src/proto/internal/*.proto -> models/internal/     (service-to-service models)
#   src/proto/common.proto     -> models/              (shared types)
#   src/proto/public/*.proto   -> src/web/src/models/  (TypeScript types)
#
# Usage:
#   ./scripts/generate_proto.sh           # Generate both Python and TypeScript
#   ./scripts/generate_proto.sh python    # Generate Python only
#   ./scripts/generate_proto.sh typescript # Generate TypeScript only
#
# Requirements:
#   Python:     pip install grpcio-tools mypy-protobuf pydantic-protobuf-gen
#   TypeScript: npm install -g ts-proto
#   Protoc:     brew install protobuf (macOS)

set -e

# Colors
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
CYAN='\033[0;36m'
NC='\033[0m'

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(dirname "$SCRIPT_DIR")"
PROTO_DIR="$PROJECT_ROOT/src/proto"
PYTHON_OUTPUT_DIR="$PROJECT_ROOT/src/echomind_lib/models"
TS_OUTPUT_DIR="$PROJECT_ROOT/src/web/src/models"

# What to generate
GENERATE_PYTHON=false
GENERATE_TYPESCRIPT=false

case "${1:-all}" in
    python)
        GENERATE_PYTHON=true
        ;;
    typescript|ts)
        GENERATE_TYPESCRIPT=true
        ;;
    all|"")
        GENERATE_PYTHON=true
        GENERATE_TYPESCRIPT=true
        ;;
    *)
        echo -e "${RED}Unknown option: $1${NC}"
        echo "Usage: $0 [python|typescript|all]"
        exit 1
        ;;
esac

echo -e "${CYAN}╔════════════════════════════════════════╗${NC}"
echo -e "${CYAN}║     EchoMind Proto Generation          ║${NC}"
echo -e "${CYAN}╚════════════════════════════════════════╝${NC}"
echo ""
echo -e "Proto source: ${YELLOW}$PROTO_DIR${NC}"
echo ""

# Collect all proto files
COMMON_PROTO="$PROTO_DIR/common.proto"
PUBLIC_PROTOS=$(find "$PROTO_DIR/public" -name "*.proto" 2>/dev/null || true)
INTERNAL_PROTOS=$(find "$PROTO_DIR/internal" -name "*.proto" 2>/dev/null || true)
ALL_PROTOS="$COMMON_PROTO $PUBLIC_PROTOS $INTERNAL_PROTOS"
PUBLIC_PROTOS_WITH_COMMON="$COMMON_PROTO $PUBLIC_PROTOS"

echo "Found proto files:"
for proto in $ALL_PROTOS; do
    echo -e "  - ${GREEN}$(basename $proto)${NC}"
done
echo ""

# ============================================
# Python Generation
# ============================================
generate_python() {
    echo -e "${CYAN}=== Generating Python Models ===${NC}"
    echo -e "Output: ${YELLOW}$PYTHON_OUTPUT_DIR${NC}"
    echo ""

    # Create output directories
    mkdir -p "$PYTHON_OUTPUT_DIR/public"
    mkdir -p "$PYTHON_OUTPUT_DIR/internal"

    # Clean old generated files
    echo "Cleaning old Python files..."
    rm -rf "$PYTHON_OUTPUT_DIR"/*.py "$PYTHON_OUTPUT_DIR"/*.pyi "$PYTHON_OUTPUT_DIR"/*.json 2>/dev/null || true
    rm -rf "$PYTHON_OUTPUT_DIR/public"/* 2>/dev/null || true
    rm -rf "$PYTHON_OUTPUT_DIR/internal"/* 2>/dev/null || true

    # Step 1: Generate all protobuf stubs and Pydantic models
    echo "Generating protobuf stubs and Pydantic models..."
    python -m grpc_tools.protoc \
        -I"$PROTO_DIR" \
        --python_out="$PYTHON_OUTPUT_DIR" \
        --pyi_out="$PYTHON_OUTPUT_DIR" \
        --pydantic_out="$PYTHON_OUTPUT_DIR" \
        $ALL_PROTOS
    echo -e "  ${GREEN}✓${NC} Generated"

    # Step 2: Move models to proper folders
    echo "Organizing files into public/internal folders..."

    for proto in $PUBLIC_PROTOS; do
        base=$(basename "$proto" .proto)
        if [ -f "$PYTHON_OUTPUT_DIR/${base}_model.py" ]; then
            mv "$PYTHON_OUTPUT_DIR/${base}_model.py" "$PYTHON_OUTPUT_DIR/public/"
        fi
    done

    for proto in $INTERNAL_PROTOS; do
        base=$(basename "$proto" .proto)
        if [ -f "$PYTHON_OUTPUT_DIR/${base}_model.py" ]; then
            mv "$PYTHON_OUTPUT_DIR/${base}_model.py" "$PYTHON_OUTPUT_DIR/internal/"
        fi
    done
    echo -e "  ${GREEN}✓${NC} Files organized"

    # Step 3: Create __init__.py files
    echo "Generating exports..."

    # Public __init__.py
    {
        echo '"""'
        echo 'Public API models - exposed to web/mobile clients.'
        echo ''
        echo 'DO NOT EDIT - Auto-generated from src/proto/public/'
        echo '"""'
        echo ''
        for py_file in "$PYTHON_OUTPUT_DIR/public"/*_model.py "$PYTHON_OUTPUT_DIR/public"/*_p2p.py; do
            if [ -f "$py_file" ]; then
                module=$(basename "$py_file" .py)
                echo "from .$module import *"
            fi
        done
    } > "$PYTHON_OUTPUT_DIR/public/__init__.py"

    # Internal __init__.py
    {
        echo '"""'
        echo 'Internal service models - backend service-to-service only.'
        echo ''
        echo 'DO NOT EDIT - Auto-generated from src/proto/internal/'
        echo '"""'
        echo ''
        for py_file in "$PYTHON_OUTPUT_DIR/internal"/*_model.py "$PYTHON_OUTPUT_DIR/internal"/*_p2p.py; do
            if [ -f "$py_file" ]; then
                module=$(basename "$py_file" .py)
                echo "from .$module import *"
            fi
        done
    } > "$PYTHON_OUTPUT_DIR/internal/__init__.py"

    # Root __init__.py
    {
        echo '"""'
        echo 'Auto-generated Pydantic models from protobuf definitions.'
        echo ''
        echo 'DO NOT EDIT - This directory is auto-generated from src/proto/'
        echo 'Regenerate with: ./scripts/generate_proto.sh'
        echo ''
        echo 'Structure:'
        echo '  models/public/   - API-facing models (User, Assistant, etc.)'
        echo '  models/internal/ - Service-to-service models (SemanticData, etc.)'
        echo ''
        echo 'Usage:'
        echo '    from echomind_lib.models.public import User, Assistant'
        echo '    from echomind_lib.models.internal import SemanticData'
        echo '"""'
        echo ''
        echo 'from .public import *'
    } > "$PYTHON_OUTPUT_DIR/__init__.py"

    echo -e "  ${GREEN}✓${NC} Exports generated"
    echo ""
    echo -e "${GREEN}✅ Python generation complete${NC}"
    echo "   Public models:   $(ls -1 "$PYTHON_OUTPUT_DIR/public"/*.py 2>/dev/null | wc -l | tr -d ' ') files"
    echo "   Internal models: $(ls -1 "$PYTHON_OUTPUT_DIR/internal"/*.py 2>/dev/null | wc -l | tr -d ' ') files"
    echo ""
}

# ============================================
# TypeScript Generation
# ============================================
generate_typescript() {
    echo -e "${CYAN}=== Generating TypeScript Types ===${NC}"
    echo -e "Output: ${YELLOW}$TS_OUTPUT_DIR${NC}"
    echo ""

    # Check if ts-proto is installed
    if ! which protoc-gen-ts_proto > /dev/null 2>&1; then
        echo -e "${RED}Error: ts-proto not found${NC}"
        echo -e "Install with: ${YELLOW}npm install -g ts-proto${NC}"
        exit 1
    fi

    # Check if protoc is installed
    if ! which protoc > /dev/null 2>&1; then
        echo -e "${RED}Error: protoc not found${NC}"
        echo -e "Install with: ${YELLOW}brew install protobuf${NC}"
        exit 1
    fi

    # Create output directory
    mkdir -p "$TS_OUTPUT_DIR"

    # Clean old generated files
    echo "Cleaning old TypeScript files..."
    rm -rf "$TS_OUTPUT_DIR"/*.ts 2>/dev/null || true
    rm -rf "$TS_OUTPUT_DIR/public" 2>/dev/null || true
    rm -rf "$TS_OUTPUT_DIR/google" 2>/dev/null || true

    # Generate TypeScript types using ts-proto
    # Options:
    #   onlyTypes=true        - Generate only interfaces (no encode/decode)
    #   stringEnums=true      - Use string enums instead of numeric
    #   useOptionals=messages - Optional fields for nested messages
    #   exportCommonSymbols=false - Avoid duplicate exports
    #   snakeToCamel=true     - Convert snake_case to camelCase
    #   outputIndex=true      - Generate index.ts files
    echo "Generating TypeScript interfaces..."
    protoc \
        -I"$PROTO_DIR" \
        --plugin=protoc-gen-ts_proto="$(which protoc-gen-ts_proto)" \
        --ts_proto_out="$TS_OUTPUT_DIR" \
        --ts_proto_opt=onlyTypes=true \
        --ts_proto_opt=stringEnums=true \
        --ts_proto_opt=useOptionals=messages \
        --ts_proto_opt=exportCommonSymbols=false \
        --ts_proto_opt=snakeToCamel=true \
        --ts_proto_opt=outputIndex=true \
        $PUBLIC_PROTOS_WITH_COMMON

    echo -e "  ${GREEN}✓${NC} Generated"

    # Create a main index.ts that re-exports everything
    echo "Creating main index.ts..."
    {
        echo '/**'
        echo ' * Auto-generated TypeScript types from protobuf definitions.'
        echo ' * '
        echo ' * DO NOT EDIT - This directory is auto-generated from src/proto/'
        echo ' * Regenerate with: ./scripts/generate_proto.sh typescript'
        echo ' */'
        echo ''
        echo "export * from './common';"
        echo "export * from './public/user';"
        echo "export * from './public/assistant';"
        echo "export * from './public/chat';"
        echo "export * from './public/connector';"
        echo "export * from './public/document';"
        echo "export * from './public/llm';"
        echo "export * from './public/embedding_model';"
    } > "$TS_OUTPUT_DIR/index.ts"

    echo -e "  ${GREEN}✓${NC} Index created"
    echo ""
    echo -e "${GREEN}✅ TypeScript generation complete${NC}"
    echo "   Generated files: $(find "$TS_OUTPUT_DIR" -name "*.ts" 2>/dev/null | wc -l | tr -d ' ') files"
    echo ""
}

# ============================================
# Main
# ============================================

if [ "$GENERATE_PYTHON" = true ]; then
    generate_python
fi

if [ "$GENERATE_TYPESCRIPT" = true ]; then
    generate_typescript
fi

echo -e "${CYAN}=== Generation Complete ===${NC}"
echo ""
echo "Import in your code:"
if [ "$GENERATE_PYTHON" = true ]; then
    echo -e "  ${GREEN}Python:${NC}     from echomind_lib.models.public import User, Assistant"
fi
if [ "$GENERATE_TYPESCRIPT" = true ]; then
    echo -e "  ${GREEN}TypeScript:${NC} import { User, Assistant } from '@/models'"
fi
echo ""