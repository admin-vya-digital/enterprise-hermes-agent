"""Security module for detecting and sanitizing PII/secrets in memory content.

This module provides functions to detect common patterns of sensitive information
(API keys, tokens, passwords, emails, IP addresses) and sanitize text by redacting
or removing them.

Used by mem_save.py to prevent accidental storage of secrets in committed memories.
"""

import re
from typing import List, Tuple

# Patterns de detecção de secrets/PII
PATTERNS = {
    "api_key": r"(api[_-]?key|apikey)\s*[=:]\s*['\"]?([a-zA-Z0-9_-]{20,})['\"]?",
    "token": r"(token|bearer)\s*[=:]\s*['\"]?([a-zA-Z0-9_-]{20,})['\"]?",
    "password": r"(password|passwd|pwd)\s*[=:]\s*['\"]?([^\s'\"]+)['\"]?",
    "email": r"\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Z|a-z]{2,}\b",
    "ip_address": r"\b(?:\d{1,3}\.){3}\d{1,3}\b",
    "aws_key": r"AKIA[0-9A-Z]{16}",
    "github_token": r"ghp_[a-zA-Z0-9]{36}",
    "jwt": r"eyJ[a-zA-Z0-9_-]*\.eyJ[a-zA-Z0-9_-]*\.[a-zA-Z0-9_-]*",
    "private_key": r"-----BEGIN (RSA |EC )?PRIVATE KEY-----",
    "slack_token": r"xox[baprs]-[0-9a-zA-Z]{10,48}",
}


def detect_secrets(text: str) -> List[Tuple[str, str]]:
    """Detect potential secrets/PII in text.

    Scans text for common patterns of sensitive information including:
    - API keys
    - Tokens (Bearer, JWT, GitHub, Slack)
    - Passwords
    - Email addresses
    - IP addresses
    - AWS access keys
    - Private keys

    Args:
        text: Input text to scan

    Returns:
        List of (pattern_name, matched_value) tuples
        Example: [("api_key", "sk_live_abc123..."), ("email", "user@example.com")]
    """
    findings = []

    for name, pattern in PATTERNS.items():
        matches = re.finditer(pattern, text, re.IGNORECASE)
        for match in matches:
            # Extract the secret value (group 2 for key=value patterns, group 0 otherwise)
            value = match.group(2) if match.lastindex and match.lastindex >= 2 else match.group(0)
            findings.append((name, value))

    return findings


def sanitize(text: str, redact: bool = True) -> Tuple[str, List[str]]:
    """Sanitize text by removing/redacting secrets.

    Replaces or removes detected secrets from text to prevent accidental
    storage of sensitive information.

    Args:
        text: Input text to sanitize
        redact: If True, replace with [REDACTED-{pattern}]; if False, remove entirely

    Returns:
        Tuple of (sanitized_text, list_of_warnings)

        sanitized_text: Text with secrets replaced/removed
        warnings: List of warning messages about what was found

        Example:
        >>> sanitize("api_key: sk_live_abc123", redact=True)
        ("api_key: [REDACTED-api_key]", ["Found 1 potential api_key(s)"])
    """
    warnings = []
    sanitized = text

    for name, pattern in PATTERNS.items():
        # Find all matches in reverse order to preserve string indices
        matches = list(re.finditer(pattern, sanitized, re.IGNORECASE))

        if matches:
            warnings.append(f"Found {len(matches)} potential {name}(s)")

            # Process matches in reverse order to preserve indices during replacement
            for match in reversed(matches):
                if redact:
                    replacement = f"[REDACTED-{name}]"
                else:
                    replacement = ""

                sanitized = sanitized[:match.start()] + replacement + sanitized[match.end():]

    return sanitized, warnings


def validate_safe(text: str, allow_emails: bool = False, allow_ips: bool = False) -> Tuple[bool, List[str]]:
    """Validate that text is safe to store (no secrets detected).

    Args:
        text: Input text to validate
        allow_emails: If True, don't flag email addresses as unsafe
        allow_ips: If True, don't flag IP addresses as unsafe

    Returns:
        Tuple of (is_safe, list_of_issues)

        is_safe: True if no secrets detected (or only allowed types)
        issues: List of detected secret types

        Example:
        >>> validate_safe("Contact: user@example.com", allow_emails=True)
        (True, [])

        >>> validate_safe("api_key: sk_live_abc123")
        (False, ["api_key"])
    """
    findings = detect_secrets(text)

    # Filter out allowed types
    filtered_findings = []
    for pattern_name, value in findings:
        if allow_emails and pattern_name == "email":
            continue
        if allow_ips and pattern_name == "ip_address":
            continue
        filtered_findings.append(pattern_name)

    # Get unique pattern names
    issues = list(set(filtered_findings))
    is_safe = len(issues) == 0

    return is_safe, issues


def get_security_report(text: str) -> str:
    """Generate a human-readable security report for text.

    Args:
        text: Input text to analyze

    Returns:
        Formatted security report string
    """
    findings = detect_secrets(text)

    if not findings:
        return "✅ No potential secrets detected"

    report = ["⚠️  Security Scan Results:", ""]

    # Group by pattern type
    by_type = {}
    for pattern_name, value in findings:
        if pattern_name not in by_type:
            by_type[pattern_name] = []
        by_type[pattern_name].append(value)

    for pattern_name, values in sorted(by_type.items()):
        report.append(f"  {pattern_name}: {len(values)} found")
        for value in values[:3]:  # Show max 3 examples
            preview = value[:20] + "..." if len(value) > 20 else value
            report.append(f"    - {preview}")
        if len(values) > 3:
            report.append(f"    ... and {len(values) - 3} more")

    return "\n".join(report)
