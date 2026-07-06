#!/usr/bin/env bash
#
# Script Name: validate-docs-links.sh
# Description: Validate all markdown links in documentation
# Usage: ./scripts/validate-docs-links.sh [--fix]
# Author: GitHub Copilot + Session Manager Agent
# Date: 2026-03-20
#

set -euo pipefail

# Colors for output
readonly RED='\033[0;31m'
readonly GREEN='\033[0;32m'
readonly YELLOW='\033[1;33m'
readonly BLUE='\033[0;34m'
readonly NC='\033[0m' # No Color

# Script directory and project root
readonly SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
readonly PROJECT_ROOT="$(cd "${SCRIPT_DIR}/.." && pwd)"

# Counters
TOTAL_FILES=0
TOTAL_LINKS=0
BROKEN_LINKS=0
FIXED_LINKS=0

# Options
FIX_MODE=false

#######################################
# Print usage information
#######################################
usage() {
    cat <<EOF
${BLUE}Documentation Link Validator${NC}

Usage: ${0##*/} [OPTIONS]

Validates all markdown links in the documentation directory.

Options:
    -f, --fix       Attempt to fix broken links automatically
    -h, --help      Show this help message
    -v, --verbose   Verbose output

Examples:
    ${0##*/}                # Check all links
    ${0##*/} --fix          # Check and attempt to fix broken links
    ${0##*/} --verbose      # Show detailed output

Exit codes:
    0    All links valid
    1    Broken links found
    2    Invalid usage
EOF
}

#######################################
# Log message with timestamp
# Arguments:
#   $1 - Log level (INFO, WARN, ERROR)
#   $2 - Message
#######################################
log() {
    local level="$1"
    shift
    local message="$*"
    local timestamp
    timestamp="$(date '+%Y-%m-%d %H:%M:%S')"

    case "$level" in
        INFO)
            echo -e "${BLUE}[${timestamp}]${NC} ${message}"
            ;;
        WARN)
            echo -e "${YELLOW}[${timestamp}] ⚠️  ${message}${NC}"
            ;;
        ERROR)
            echo -e "${RED}[${timestamp}] ❌ ${message}${NC}"
            ;;
        SUCCESS)
            echo -e "${GREEN}[${timestamp}] ✅ ${message}${NC}"
            ;;
    esac
}

#######################################
# Extract markdown links from file
# Arguments:
#   $1 - File path
# Outputs:
#   List of links (one per line)
#######################################
extract_links() {
    local file="$1"

    # Extract markdown links: [text](url)
    # Also extract reference-style links: [text][ref] and [ref]: url
    grep -oP '\[([^\]]+)\]\(([^\)]+)\)|\[([^\]]+)\]:\s*(\S+)' "$file" 2>/dev/null | \
        sed -E 's/\[([^\]]+)\]\(([^\)]+)\)/\2/' | \
        sed -E 's/\[([^\]]+)\]:\s*(\S+)/\2/' || true
}

#######################################
# Check if link is valid
# Arguments:
#   $1 - Link URL
#   $2 - Source file path
# Returns:
#   0 if valid, 1 if broken
#######################################
check_link() {
    local link="$1"
    local source_file="$2"
    local source_dir
    source_dir="$(dirname "$source_file")"

    # Skip external URLs (http, https, ftp, mailto)
    if [[ "$link" =~ ^(https?|ftp|mailto): ]]; then
        return 0
    fi

    # Skip anchors without file reference
    if [[ "$link" =~ ^# ]]; then
        # TODO: Validate anchor exists in current file
        return 0
    fi

    # Remove anchor from link
    local file_path="${link%%#*}"

    # Resolve relative path
    local full_path
    if [[ "$file_path" = /* ]]; then
        # Absolute path from project root
        full_path="${PROJECT_ROOT}${file_path}"
    else
        # Relative path from source file
        full_path="${source_dir}/${file_path}"
    fi

    # Normalize path
    full_path="$(cd "$(dirname "$full_path")" 2>/dev/null && pwd)/$(basename "$full_path")" || return 1

    # Check if file/directory exists
    if [[ -e "$full_path" ]]; then
        return 0
    else
        return 1
    fi
}

#######################################
# Suggest fix for broken link
# Arguments:
#   $1 - Broken link
#   $2 - Source file
# Outputs:
#   Suggested fix or empty string
#######################################
suggest_fix() {
    local link="$1"
    local source_file="$2"
    local filename
    filename="$(basename "${link%%#*}")"

    # Search for file with same name in project
    local found_files
    found_files="$(find "${PROJECT_ROOT}" -type f -name "$filename" 2>/dev/null | head -5)"

    if [[ -n "$found_files" ]]; then
        log INFO "  Possible matches for '$filename':"
        while IFS= read -r found_file; do
            local rel_path
            rel_path="$(realpath --relative-to="$(dirname "$source_file")" "$found_file")"
            echo "    - $rel_path"
        done <<< "$found_files"
    fi
}

#######################################
# Process single markdown file
# Arguments:
#   $1 - File path
#######################################
process_file() {
    local file="$1"
    local rel_path
    rel_path="$(realpath --relative-to="$PROJECT_ROOT" "$file")"

    log INFO "Checking ${BLUE}$rel_path${NC}"

    ((TOTAL_FILES++))

    local links
    links="$(extract_links "$file")"

    if [[ -z "$links" ]]; then
        return 0
    fi

    local file_broken=0

    while IFS= read -r link; do
        ((TOTAL_LINKS++))

        if ! check_link "$link" "$file"; then
            ((BROKEN_LINKS++))
            ((file_broken++))

            log ERROR "  Broken link: ${RED}$link${NC}"

            if [[ "$FIX_MODE" = true ]]; then
                suggest_fix "$link" "$file"
            fi
        fi
    done <<< "$links"

    if [[ $file_broken -eq 0 ]]; then
        log SUCCESS "  All links valid"
    else
        log WARN "  Found $file_broken broken link(s)"
    fi
}

#######################################
# Main validation process
#######################################
validate_all_docs() {
    log INFO "Starting documentation link validation"
    log INFO "Project root: $PROJECT_ROOT"
    echo ""

    # Find all markdown files in project
    local md_files
    md_files="$(find "$PROJECT_ROOT" -type f -name "*.md" \
        -not -path "*/.git/*" \
        -not -path "*/node_modules/*" \
        -not -path "*/.venv/*" \
        -not -path "*/venv/*" \
        2>/dev/null)"

    if [[ -z "$md_files" ]]; then
        log WARN "No markdown files found"
        return 0
    fi

    # Process each file
    while IFS= read -r file; do
        process_file "$file"
        echo ""
    done <<< "$md_files"

    # Summary
    echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
    log INFO "Validation Summary:"
    echo "  Files checked:   $TOTAL_FILES"
    echo "  Links checked:   $TOTAL_LINKS"

    if [[ $BROKEN_LINKS -eq 0 ]]; then
        log SUCCESS "All links valid! ✨"
        return 0
    else
        log ERROR "Found $BROKEN_LINKS broken link(s) ⚠️"

        if [[ "$FIX_MODE" = false ]]; then
            echo ""
            log INFO "Run with ${BLUE}--fix${NC} to see suggestions for fixing broken links"
        fi

        return 1
    fi
}

#######################################
# Parse command line arguments
#######################################
parse_args() {
    while [[ $# -gt 0 ]]; do
        case "$1" in
            -f|--fix)
                FIX_MODE=true
                shift
                ;;
            -h|--help)
                usage
                exit 0
                ;;
            -v|--verbose)
                set -x
                shift
                ;;
            *)
                log ERROR "Unknown option: $1"
                usage
                exit 2
                ;;
        esac
    done
}

#######################################
# Main
#######################################
main() {
    parse_args "$@"

    cd "$PROJECT_ROOT" || {
        log ERROR "Failed to change to project root: $PROJECT_ROOT"
        exit 1
    }

    validate_all_docs
}

# Run main if executed directly
if [[ "${BASH_SOURCE[0]}" == "${0}" ]]; then
    main "$@"
fi
