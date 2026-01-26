# Proto compilation Makefile
# Generates Python and TypeScript types from .proto files
#
# Usage:
#   make python      - Generate Python protobuf + Pydantic models
#   make typescript  - Generate TypeScript interfaces
#   make all         - Generate both Python and TypeScript
#   make clean       - Remove generated files
#
# Requirements:
#   Python:     pip install grpcio-tools pydantic-protobuf-gen
#   TypeScript: npm install -g ts-proto

PROTO_DIR := .
PUBLIC_DIR := public
INTERNAL_DIR := internal
PYTHON_OUT := ../echomind_lib/models
TS_OUT := ../web/src/models

# Proto compiler
PROTOC := protoc

# Find all proto files
PUBLIC_PROTOS := $(wildcard $(PUBLIC_DIR)/*.proto)
INTERNAL_PROTOS := $(wildcard $(INTERNAL_DIR)/*.proto)
COMMON_PROTO := common.proto

.PHONY: all clean python typescript check-protoc check-ts-proto

all: python typescript

# Check if protoc is installed
check-protoc:
	@which protoc > /dev/null || (echo "Error: protoc not found. Install with: brew install protobuf" && exit 1)

# Check if ts-proto is installed
check-ts-proto:
	@which protoc-gen-ts_proto > /dev/null || (echo "Error: ts-proto not found. Install with: npm install -g ts-proto" && exit 1)

# Generate Python protobuf stubs + Pydantic models
python: check-protoc
	@echo "=== Generating Python protobuf and Pydantic models ==="
	@mkdir -p $(PYTHON_OUT)/public $(PYTHON_OUT)/internal
	python -m grpc_tools.protoc \
		-I$(PROTO_DIR) \
		--python_out=$(PYTHON_OUT) \
		--pyi_out=$(PYTHON_OUT) \
		--grpc_python_out=$(PYTHON_OUT) \
		--pydantic_out=$(PYTHON_OUT) \
		$(COMMON_PROTO) \
		$(PUBLIC_DIR)/*.proto \
		$(INTERNAL_DIR)/*.proto
	@echo "✅ Python models generated in $(PYTHON_OUT)"

# Generate TypeScript interfaces using ts-proto
# Options:
#   onlyTypes=true        - Generate only interfaces (no encode/decode)
#   stringEnums=true      - Use string enums instead of numeric
#   useOptionals=messages - Optional fields for nested messages
#   exportCommonSymbols=false - Avoid duplicate exports
#   snakeToCamel=true     - Convert snake_case to camelCase
typescript: check-protoc check-ts-proto
	@echo "=== Generating TypeScript types ==="
	@mkdir -p $(TS_OUT)
	protoc \
		-I$(PROTO_DIR) \
		--plugin=protoc-gen-ts_proto=$$(which protoc-gen-ts_proto) \
		--ts_proto_out=$(TS_OUT) \
		--ts_proto_opt=onlyTypes=true \
		--ts_proto_opt=stringEnums=true \
		--ts_proto_opt=useOptionals=messages \
		--ts_proto_opt=exportCommonSymbols=false \
		--ts_proto_opt=snakeToCamel=true \
		--ts_proto_opt=outputIndex=true \
		$(COMMON_PROTO) \
		$(PUBLIC_DIR)/*.proto
	@echo "✅ TypeScript types generated in $(TS_OUT)"
	@echo ""
	@echo "Import in your React/TypeScript code:"
	@echo "  import { User, Assistant, ChatSession } from '@/models'"

# Clean generated files
clean:
	@echo "Cleaning generated files..."
	rm -rf $(PYTHON_OUT)/*.py $(PYTHON_OUT)/*.pyi $(PYTHON_OUT)/*.json 2>/dev/null || true
	rm -rf $(PYTHON_OUT)/public/* $(PYTHON_OUT)/internal/* 2>/dev/null || true
	rm -rf $(TS_OUT)/*.ts 2>/dev/null || true
	@echo "✅ Clean complete"

# Install all dependencies
install-deps:
	@echo "Installing Python dependencies..."
	pip install grpcio-tools protobuf pydantic-protobuf-gen
	@echo ""
	@echo "Installing TypeScript dependencies..."
	npm install -g ts-proto
	@echo ""
	@echo "Installing protoc (macOS)..."
	@which protoc > /dev/null || brew install protobuf
	@echo ""
	@echo "✅ All dependencies installed"

# Help
help:
	@echo "EchoMind Proto Generation"
	@echo ""
	@echo "Usage:"
	@echo "  make python      - Generate Python protobuf + Pydantic models"
	@echo "  make typescript  - Generate TypeScript interfaces"
	@echo "  make all         - Generate both"
	@echo "  make clean       - Remove generated files"
	@echo "  make install-deps - Install required dependencies"
	@echo ""
	@echo "Output:"
	@echo "  Python:     $(PYTHON_OUT)/"
	@echo "  TypeScript: $(TS_OUT)/"