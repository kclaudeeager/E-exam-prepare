#!/bin/bash
# Groq Integration Verification Script
# Run this to verify Groq is properly integrated

set -e

echo "╔════════════════════════════════════════════════════════════════╗"
echo "║          Groq Integration Verification                        ║"
echo "║     E-exam-prepare RAG Service Configuration Check            ║"
echo "╚════════════════════════════════════════════════════════════════╝"
echo ""

PROJECT_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$PROJECT_ROOT"

# Colors
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Counters
PASSED=0
FAILED=0

check_file() {
    local file="$1"
    local description="$2"
    
    if [ -f "$file" ]; then
        echo -e "${GREEN}✅${NC} $description"
        echo "   Path: $file"
        ((PASSED++))
    else
        echo -e "${RED}❌${NC} $description"
        echo "   Path: $file (NOT FOUND)"
        ((FAILED++))
    fi
}

check_content() {
    local file="$1"
    local pattern="$2"
    local description="$3"
    
    if grep -q "$pattern" "$file" 2>/dev/null; then
        echo -e "${GREEN}✅${NC} $description"
        ((PASSED++))
    else
        echo -e "${RED}❌${NC} $description"
        echo "   Expected pattern: $pattern"
        echo "   In file: $file"
        ((FAILED++))
    fi
}

echo "📋 Checking Files..."
echo ""

# Core files
check_file "rag-service/app/config.py" "RAG config exists"
check_file "rag-service/app/rag/engine.py" "RAG engine exists"
check_file "rag-service/app/providers.py" "Provider factory exists"
check_file "rag-service/app/llms/groq_llm.py" "Custom Groq LLM implementation"
check_file "rag-service/pyproject.toml" "RAG dependencies defined"

echo ""
echo "🔍 Checking Configuration..."
echo ""

# Configuration checks
check_content "rag-service/app/config.py" "LLAMA_INDEX_PROVIDER.*groq" "Groq set as default provider"
check_content "rag-service/app/config.py" "GROQ_API_KEY" "Groq API key field exists"
check_content "rag-service/app/rag/engine.py" "elif provider == \"groq\"" "Groq support in engine"
check_content "rag-service/app/providers.py" "elif provider == \"groq\"" "Groq support in providers"
check_content "rag-service/pyproject.toml" "llama-index-llms-groq" "Groq LlamaIndex integration in dependencies"

echo ""
echo "📚 Checking Documentation..."
echo ""

# Documentation
check_file "GROQ_SETUP.md" "Groq setup guide (RAG service)"
check_file "GROQ_INTEGRATION.md" "Groq integration summary"
check_file "SETUP_GUIDE.md" "Complete setup guide"
check_file "GROQ_CHANGES.md" "Changes summary"

echo ""
echo "🔧 Checking Dependencies..."
echo ""

# Try to import and verify
cd rag-service
echo -n "   Checking if dependencies can be imported... "
if uv run python -c "from app.config import settings; print(f'Provider: {settings.LLAMA_INDEX_PROVIDER}')" > /tmp/groq_check.txt 2>&1; then
    PROVIDER=$(cat /tmp/groq_check.txt | grep "Provider:" | awk '{print $NF}')
    if [ "$PROVIDER" == "groq" ]; then
        echo -e "${GREEN}✅${NC} Groq is default provider"
        ((PASSED++))
    else
        echo -e "${YELLOW}⚠️${NC}  Provider is $PROVIDER (not groq)"
    fi
else
    echo -e "${RED}❌${NC} Failed to import"
    cat /tmp/groq_check.txt
    ((FAILED++))
fi

cd "$PROJECT_ROOT"

echo ""
echo "═══════════════════════════════════════════════════════════════"
echo ""
echo -e "Summary: ${GREEN}$PASSED passed${NC}, ${RED}$FAILED failed${NC}"
echo ""

if [ $FAILED -eq 0 ]; then
    echo -e "${GREEN}✅ All checks passed! Groq is properly integrated.${NC}"
    echo ""
    echo "Next steps:"
    echo "  1. Get Groq API key: https://console.groq.com"
    echo "  2. Set GROQ_API_KEY in .env files"
    echo "  3. Start RAG service: cd rag-service && uv run uvicorn app.main:app --port 8001"
    echo "  4. Start backend: cd backend && uv run uvicorn app.main:app --port 8000"
    echo "  5. Start frontend: cd frontend && npm run dev"
    echo ""
    exit 0
else
    echo -e "${RED}❌ Some checks failed. Review the output above.${NC}"
    exit 1
fi
