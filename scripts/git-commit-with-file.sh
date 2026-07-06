#!/usr/bin/env bash
# git-commit-with-file.sh - Commit using message from file
# Usage: ./git-commit-with-file.sh <commit-message-file>

set -euo pipefail

# Colors
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

# Check arguments
if [ $# -eq 0 ]; then
    echo -e "${RED}❌ ERROR: No commit message file provided${NC}"
    echo "Usage: $0 <commit-message-file>"
    exit 1
fi

COMMIT_FILE="$1"

# Check if file exists
if [ ! -f "$COMMIT_FILE" ]; then
    echo -e "${RED}❌ ERROR: Commit message file not found: $COMMIT_FILE${NC}"
    exit 1
fi

# Check if file is empty
if [ ! -s "$COMMIT_FILE" ]; then
    echo -e "${RED}❌ ERROR: Commit message file is empty${NC}"
    exit 1
fi

# Validate commit message format (first line should follow Conventional Commits)
FIRST_LINE=$(head -n 1 "$COMMIT_FILE")
if ! echo "$FIRST_LINE" | grep -qE '^(feat|fix|docs|refactor|test|chore|perf|ci|security)(\(.+\))?: .+'; then
    echo -e "${YELLOW}⚠️  WARNING: Commit message does not follow Conventional Commits format${NC}"
    echo "Expected: type(scope): description"
    echo "Got: $FIRST_LINE"
    read -p "Continue anyway? (y/N) " -n 1 -r
    echo
    if [[ ! $REPLY =~ ^[Yy]$ ]]; then
        echo -e "${RED}❌ Commit aborted${NC}"
        exit 1
    fi
fi

# Show changes to be committed
echo -e "${YELLOW}📋 Changes to be committed:${NC}"
git status --short

# Show commit message
echo -e "\n${YELLOW}📝 Commit message:${NC}"
echo "---"
cat "$COMMIT_FILE"
echo "---"

# Confirm commit
read -p "Proceed with commit? (y/N) " -n 1 -r
echo
if [[ ! $REPLY =~ ^[Yy]$ ]]; then
    echo -e "${RED}❌ Commit aborted${NC}"
    exit 1
fi

# Perform commit
git commit -F "$COMMIT_FILE"

if [ $? -eq 0 ]; then
    echo -e "${GREEN}✅ Commit successful${NC}"

    # Show last commit
    echo -e "\n${GREEN}📊 Last commit:${NC}"
    git log -1 --oneline

    # Cleanup commit file
    rm -f "$COMMIT_FILE"
    echo -e "${GREEN}🗑️  Commit message file cleaned up${NC}"
else
    echo -e "${RED}❌ Commit failed${NC}"
    exit 1
fi
