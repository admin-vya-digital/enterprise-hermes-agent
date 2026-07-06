#!/usr/bin/env python3
"""
Session Documentation Validator

Validates format and structure of DAILY_ACTIVITIES_*.md files against
the canonical template defined in SESSION_DOCS_STYLE_GUIDE.md.

Part of: IMP-49 — Sistema de documentação incremental — Integração
Created: 2026-04-03

Usage:
    python scripts/session-validate.py docs/SESSIONS/2026-04-03/DAILY_ACTIVITIES_2026-04-03.md
    python scripts/session-validate.py docs/SESSIONS/2026-04-03/  # all DAILY_ACTIVITIES in dir
    python scripts/session-validate.py --all  # all DAILY_ACTIVITIES in docs/SESSIONS/
"""

import argparse
import re
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import List, Optional, Dict, Tuple

# ANSI color codes
GREEN = "\033[92m"
YELLOW = "\033[93m"
RED = "\033[91m"
BLUE = "\033[94m"
RESET = "\033[0m"


@dataclass
class ActivityBlock:
    """Represents one activity block from DAILY_ACTIVITIES."""

    raw_content: str
    start_line: int
    title: Optional[str] = None
    timestamp: Optional[str] = None
    status_marker: Optional[str] = None
    has_objetivo: bool = False
    has_contexto: bool = False
    has_passos: bool = False
    has_resultado: bool = False
    has_status: bool = False
    has_separator: bool = False


@dataclass
class ValidationResult:
    """Result of validating one DAILY_ACTIVITIES file."""

    file_path: Path
    blocks: List[ActivityBlock]
    errors: List[str]
    warnings: List[str]
    suspicious_patterns: List[Tuple[int, str, str]]  # (line_num, pattern, matched_text)


class SessionValidator:
    """Validates session documentation format."""

    # Required fields in canonical template
    REQUIRED_FIELDS = ["Objetivo", "Contexto", "Passos executados", "Resultado", "Status"]

    # Valid status values
    VALID_STATUSES = [
        "✅ Completo",
        "🔵 Em progresso",
        "❌ Bloqueado",
        "⏸️ On hold",
    ]

    # Suspicious patterns (potential sensitive data)
    SUSPICIOUS_PATTERNS = {
        "api_key": re.compile(r"(?i)(api[_-]?key|apikey)\s*[:=]\s*['\"]?[0-9a-zA-Z\-_]{20,}", re.IGNORECASE),
        "bearer_token": re.compile(r"Bearer\s+[A-Za-z0-9\-_\.]{20,}"),
        "jwt": re.compile(r"eyJ[A-Za-z0-9_-]{10,}\.eyJ[A-Za-z0-9_-]{10,}\.[A-Za-z0-9_-]{10,}"),
        "password": re.compile(r"(?i)(password|passwd|pwd)\s*[:=]\s*['\"]?[^\s'\"\n]{8,}", re.IGNORECASE),
        "private_ip_10": re.compile(r"(?<!\.)10\.(\d{1,3}\.){2}\d{1,3}(?!\.)"),
        "private_ip_172": re.compile(r"(?<!\.)172\.(1[6-9]|2[0-9]|3[01])\.(\d{1,3}\.)\d{1,3}(?!\.)"),
        "private_ip_192": re.compile(r"(?<!\.)192\.168\.(\d{1,3}\.)\d{1,3}(?!\.)"),
        "github_token": re.compile(r"ghp_[0-9a-zA-Z]{36}"),
    }

    # Allowlisted patterns (sanitized examples)
    ALLOWLIST_PATTERNS = [
        re.compile(r"(example|sample|test|mock|dummy)_?(key|token|password|secret)", re.IGNORECASE),
        re.compile(r"<(TOKEN|API_KEY|SECRET|REDACTED)>"),
        re.compile(r"\*{3,}"),  # Redacted with asterisks
        re.compile(r"user@example\.(com|org|net)"),
        re.compile(r"192\.0\.2\.\d+"),  # TEST-NET-1 (RFC 5737)
        re.compile(r"198\.51\.100\.\d+"),  # TEST-NET-2
        re.compile(r"203\.0\.113\.\d+"),  # TEST-NET-3
    ]

    def __init__(self):
        self.errors_count = 0
        self.warnings_count = 0
        self.files_validated = 0
        self.blocks_validated = 0

    def parse_activity_blocks(self, content: str) -> List[ActivityBlock]:
        """Parse DAILY_ACTIVITIES content into individual blocks."""
        blocks = []
        lines = content.split("\n")

        # Find all block separators (---)
        separator_indices = [i for i, line in enumerate(lines) if line.strip() == "---"]

        # Extract blocks between separators
        for i in range(len(separator_indices) - 1):
            start_idx = separator_indices[i] + 1
            end_idx = separator_indices[i + 1]
            block_lines = lines[start_idx:end_idx]
            block_content = "\n".join(block_lines)

            if block_content.strip():  # Skip empty blocks
                block = self._parse_single_block(block_content, start_idx + 1)
                blocks.append(block)

        return blocks

    def _parse_single_block(self, content: str, start_line: int) -> ActivityBlock:
        """Parse a single activity block."""
        block = ActivityBlock(raw_content=content, start_line=start_line)

        # Extract title (### Title (TODO-ID))
        title_match = re.search(r"^### (.+)", content, re.MULTILINE)
        if title_match:
            block.title = title_match.group(1).strip()

        # Extract timestamp and status marker (HH:MM — STATUS)
        timestamp_match = re.search(r"\*\*(\d{2}:\d{2})\s*—\s*(.+?)\*\*", content)
        if timestamp_match:
            block.timestamp = timestamp_match.group(1)
            block.status_marker = timestamp_match.group(2).strip("[]")

        # Check for required fields
        block.has_objetivo = bool(re.search(r"\*\*Objetivo\*\*:", content))
        block.has_contexto = bool(re.search(r"\*\*Contexto\*\*:", content))
        block.has_passos = bool(re.search(r"\*\*Passos executados\*\*:", content))
        block.has_resultado = bool(re.search(r"\*\*Resultado\*\*:", content))
        block.has_status = bool(re.search(r"\*\*Status\*\*:", content))

        # Check if block ends with separator
        block.has_separator = content.rstrip().endswith("---")

        return block

    def validate_block(self, block: ActivityBlock, file_path: Path) -> Tuple[List[str], List[str]]:
        """Validate a single activity block. Returns (errors, warnings)."""
        errors = []
        warnings = []

        # Check title
        if not block.title:
            errors.append(f"[Line {block.start_line}] Missing title (### Title format)")
        elif len(block.title) > 100:
            warnings.append(f"[Line {block.start_line}] Title too long ({len(block.title)} chars, recommended ≤70)")

        # Check timestamp
        if not block.timestamp:
            errors.append(f"[Line {block.start_line}] Missing timestamp (HH:MM format)")
        elif not re.match(r"^\d{2}:\d{2}$", block.timestamp):
            errors.append(f"[Line {block.start_line}] Invalid timestamp format: {block.timestamp} (should be HH:MM)")

        # Check required fields
        for field in ["objetivo", "contexto", "passos", "resultado", "status"]:
            if not getattr(block, f"has_{field}"):
                errors.append(
                    f"[Line {block.start_line}] Missing required field: **{field.capitalize()}**:"
                )

        # Check status value
        if block.has_status:
            status_match = re.search(r"\*\*Status\*\*:\s*(.+?)(?:\n|$)", block.raw_content)
            if status_match:
                status_value = status_match.group(1).strip()
                if status_value not in self.VALID_STATUSES:
                    warnings.append(
                        f"[Line {block.start_line}] Non-standard status: {status_value} "
                        f"(expected one of: {', '.join(self.VALID_STATUSES)})"
                    )

        return errors, warnings

    def scan_for_suspicious_patterns(
        self, content: str, file_path: Path
    ) -> List[Tuple[int, str, str]]:
        """Scan content for potentially sensitive data."""
        findings = []
        lines = content.split("\n")

        for line_num, line in enumerate(lines, start=1):
            # Check if line is allowlisted (sanitized example)
            if any(pattern.search(line) for pattern in self.ALLOWLIST_PATTERNS):
                continue

            # Check for suspicious patterns
            for pattern_name, pattern in self.SUSPICIOUS_PATTERNS.items():
                match = pattern.search(line)
                if match:
                    findings.append((line_num, pattern_name, match.group(0)))

        return findings

    def validate_file(self, file_path: Path) -> ValidationResult:
        """Validate a single DAILY_ACTIVITIES file."""
        if not file_path.exists():
            return ValidationResult(
                file_path=file_path,
                blocks=[],
                errors=[f"File not found: {file_path}"],
                warnings=[],
                suspicious_patterns=[],
            )

        content = file_path.read_text(encoding="utf-8")
        blocks = self.parse_activity_blocks(content)

        all_errors = []
        all_warnings = []

        # Validate each block
        for block in blocks:
            errors, warnings = self.validate_block(block, file_path)
            all_errors.extend(errors)
            all_warnings.extend(warnings)

        # Scan for suspicious patterns
        suspicious = self.scan_for_suspicious_patterns(content, file_path)

        return ValidationResult(
            file_path=file_path,
            blocks=blocks,
            errors=all_errors,
            warnings=all_warnings,
            suspicious_patterns=suspicious,
        )

    def print_result(self, result: ValidationResult, verbose: bool = False):
        """Print validation result to stdout."""
        print(f"\n{BLUE}📄 {result.file_path.name}{RESET}")
        print(f"   Blocks: {len(result.blocks)}")

        if result.errors:
            print(f"\n{RED}❌ Errors ({len(result.errors)}):{RESET}")
            for error in result.errors:
                print(f"   {error}")
            self.errors_count += len(result.errors)

        if result.warnings:
            print(f"\n{YELLOW}⚠️  Warnings ({len(result.warnings)}):{RESET}")
            for warning in result.warnings:
                print(f"   {warning}")
            self.warnings_count += len(result.warnings)

        if result.suspicious_patterns:
            print(f"\n{YELLOW}🔍 Suspicious patterns ({len(result.suspicious_patterns)}):{RESET}")
            for line_num, pattern_name, matched_text in result.suspicious_patterns:
                # Truncate matched text if too long
                display_text = matched_text[:50] + "..." if len(matched_text) > 50 else matched_text
                print(f"   Line {line_num}: {pattern_name} → {display_text}")

        if not result.errors and not result.warnings and not result.suspicious_patterns:
            print(f"   {GREEN}✅ Valid{RESET}")

        self.files_validated += 1
        self.blocks_validated += len(result.blocks)

    def validate_directory(self, directory: Path, verbose: bool = False) -> List[ValidationResult]:
        """Validate all DAILY_ACTIVITIES files in a directory."""
        files = sorted(directory.glob("DAILY_ACTIVITIES_*.md"))

        if not files:
            print(f"{YELLOW}⚠️  No DAILY_ACTIVITIES_*.md files found in {directory}{RESET}")
            return []

        results = []
        for file_path in files:
            result = self.validate_file(file_path)
            self.print_result(result, verbose)
            results.append(result)

        return results

    def print_summary(self):
        """Print validation summary."""
        print(f"\n{BLUE}{'=' * 60}{RESET}")
        print(f"{BLUE}📊 Validation Summary{RESET}")
        print(f"{BLUE}{'=' * 60}{RESET}")
        print(f"Files validated: {self.files_validated}")
        print(f"Blocks validated: {self.blocks_validated}")

        if self.errors_count > 0:
            print(f"{RED}Errors: {self.errors_count}{RESET}")
        else:
            print(f"{GREEN}Errors: 0{RESET}")

        if self.warnings_count > 0:
            print(f"{YELLOW}Warnings: {self.warnings_count}{RESET}")
        else:
            print(f"{GREEN}Warnings: 0{RESET}")

        if self.errors_count == 0 and self.warnings_count == 0:
            print(f"\n{GREEN}✅ All validations passed!{RESET}")
            return 0
        elif self.errors_count > 0:
            print(f"\n{RED}❌ Validation failed with errors{RESET}")
            return 1
        else:
            print(f"\n{YELLOW}⚠️  Validation passed with warnings{RESET}")
            return 0


def main():
    """Main CLI entry point."""
    parser = argparse.ArgumentParser(
        description="Validate session documentation format",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Validate single file
  %(prog)s docs/SESSIONS/2026-04-03/DAILY_ACTIVITIES_2026-04-03.md

  # Validate all files in directory
  %(prog)s docs/SESSIONS/2026-04-03/

  # Validate all session docs
  %(prog)s --all

  # Verbose output
  %(prog)s --all --verbose
""",
    )

    parser.add_argument(
        "path",
        nargs="?",
        type=Path,
        help="Path to DAILY_ACTIVITIES file or directory",
    )
    parser.add_argument(
        "--all",
        action="store_true",
        help="Validate all DAILY_ACTIVITIES files in docs/SESSIONS/",
    )
    parser.add_argument(
        "-v", "--verbose",
        action="store_true",
        help="Verbose output",
    )

    args = parser.parse_args()

    validator = SessionValidator()

    # Determine what to validate
    if args.all:
        sessions_dir = Path("docs/SESSIONS")
        if not sessions_dir.exists():
            print(f"{RED}❌ Error: docs/SESSIONS/ directory not found{RESET}")
            return 1

        # Find all session directories and validate
        for session_dir in sorted(sessions_dir.glob("*/"), reverse=True):
            validator.validate_directory(session_dir, args.verbose)

    elif args.path:
        if args.path.is_file():
            result = validator.validate_file(args.path)
            validator.print_result(result, args.verbose)
        elif args.path.is_dir():
            validator.validate_directory(args.path, args.verbose)
        else:
            print(f"{RED}❌ Error: {args.path} is not a file or directory{RESET}")
            return 1
    else:
        parser.print_help()
        return 1

    # Print summary and exit
    exit_code = validator.print_summary()
    return exit_code


if __name__ == "__main__":
    sys.exit(main())
