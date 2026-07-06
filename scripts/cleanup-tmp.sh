#!/usr/bin/env bash

# cleanup-tmp.sh
# Clean temporary files from project's tmp/ directory
# Usage: ./scripts/cleanup-tmp.sh [--dry-run] [--verbose]

set -euo pipefail

# Colors
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Project root (script location independent)
PROJECT_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
TMP_DIR="${PROJECT_ROOT}/tmp"

# Options
DRY_RUN=false
VERBOSE=false

# Parse arguments
while [[ $# -gt 0 ]]; do
    case $1 in
        --dry-run)
            DRY_RUN=true
            shift
            ;;
        --verbose|-v)
            VERBOSE=true
            shift
            ;;
        --help|-h)
            echo "Usage: $0 [OPTIONS]"
            echo ""
            echo "Clean temporary files from project's tmp/ directory"
            echo ""
            echo "Options:"
            echo "  --dry-run     Show what would be deleted without actually deleting"
            echo "  --verbose,-v  Show detailed information"
            echo "  --help,-h     Show this help message"
            echo ""
            echo "Example:"
            echo "  $0                 # Clean tmp/ directory"
            echo "  $0 --dry-run       # Show what would be deleted"
            echo "  $0 --verbose       # Clean with detailed output"
            exit 0
            ;;
        *)
            echo -e "${RED}✗ Unknown option: $1${NC}"
            echo "Use --help for usage information"
            exit 1
            ;;
    esac
done

# Ensure tmp directory exists
if [[ ! -d "$TMP_DIR" ]]; then
    if [[ "$VERBOSE" == "true" ]]; then
        echo -e "${YELLOW}ℹ tmp/ directory does not exist, creating it...${NC}"
    fi
    mkdir -p "$TMP_DIR"
    exit 0
fi

# Function to log messages
log_info() {
    if [[ "$VERBOSE" == "true" ]]; then
        echo -e "${BLUE}ℹ $1${NC}"
    fi
}

log_success() {
    echo -e "${GREEN}✓ $1${NC}"
}

log_warning() {
    echo -e "${YELLOW}⚠ $1${NC}"
}

log_error() {
    echo -e "${RED}✗ $1${NC}"
}

# Count files before cleanup (excluding README.md)
file_count=$(find "$TMP_DIR" -type f ! -name "README.md" | wc -l)
dir_count=$(find "$TMP_DIR" -mindepth 1 -type d | wc -l)

if [[ "$file_count" -eq 0 ]] && [[ "$dir_count" -eq 0 ]]; then
    log_success "tmp/ directory is already clean (only README.md present)"
    exit 0
fi

log_info "Found $file_count file(s) and $dir_count directory(ies) to clean"

if [[ "$DRY_RUN" == "true" ]]; then
    echo -e "${YELLOW}🔍 DRY RUN MODE - No files will be deleted${NC}"
    echo ""
fi

# Calculate total size
total_size=$(du -sh "$TMP_DIR" 2>/dev/null | cut -f1)
log_info "Current tmp/ size: $total_size"

# List files to be deleted
if [[ "$VERBOSE" == "true" ]] || [[ "$DRY_RUN" == "true" ]]; then
    echo ""
    echo "Files and directories to be removed:"
    find "$TMP_DIR" -mindepth 1 ! -name "README.md" ! -path "$TMP_DIR/README.md" -print | while read -r item; do
        if [[ -f "$item" ]]; then
            size=$(du -h "$item" 2>/dev/null | cut -f1)
            echo "  📄 $item ($size)"
        elif [[ -d "$item" ]]; then
            size=$(du -sh "$item" 2>/dev/null | cut -f1)
            echo "  📁 $item/ ($size)"
        fi
    done
    echo ""
fi

# Perform cleanup
if [[ "$DRY_RUN" == "false" ]]; then
    # Remove all files except README.md
    find "$TMP_DIR" -mindepth 1 -type f ! -name "README.md" -delete 2>/dev/null || true

    # Remove all directories
    find "$TMP_DIR" -mindepth 1 -type d -exec rm -rf {} + 2>/dev/null || true

    # Verify cleanup
    remaining_count=$(find "$TMP_DIR" -type f ! -name "README.md" | wc -l)

    if [[ "$remaining_count" -eq 0 ]]; then
        log_success "Cleaned $file_count file(s) and $dir_count directory(ies) from tmp/"
        log_info "tmp/README.md preserved ✓"
    else
        log_warning "Some files could not be removed ($remaining_count remaining)"
        exit 1
    fi
else
    echo -e "${YELLOW}✓ Dry run complete - no changes made${NC}"
fi

exit 0
