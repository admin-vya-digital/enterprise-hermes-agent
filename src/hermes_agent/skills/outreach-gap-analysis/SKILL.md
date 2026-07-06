---
name: outreach-gap-analysis
summary: Verify campaign coverage by matching an eligibility rule against outreach logs using set operations.
description: End-to-end pattern for verifying outreach coverage against business rules (e.g., days-in-arrears buckets), handling messy API exports and producing per-segment gap reports.
tags: [data-science, analytics, verification]
---

# Outreach Gap Analysis

Verify whether a rule-based outreach campaign actually reached all intended contacts by comparing the eligible set (from source data) against what was logged as sent.

## When to use

- You have a source dataset (API JSON or CSV) and outreach logs (CSV) with a shared key field (CPF/CNPJ)
- You need to prove coverage against a rule (e.g., DIAS_DE_ATRASO ∈ {5,15,20,30,40,50,60})
- You want per-segment analysis (PF vs PJ) and an actionable "not contacted" export

## Workflow

1. **Extract source data**
   - If the file has line-number prefixes (`123| {...}`), split each line on the first `|` and keep only the remainder.
   - Isolate the JSON block by finding the first `{`/`[` and the last `}`/`]`.

2. **Normalize fields**
   - Coerce numeric rule fields (e.g., DIAS_DE_ATRASO) to int with try/except fallback.
   - Normalize enums (TIPO_PESSOA) to uppercase: `.strip().upper()`.

3. **Apply eligibility rules**
   - Filter records where the rule predicate matches.
   - Split into segments (PF vs PJ) if the rule differs by segment.

4. **Load outreach logs**
   - Parse CSVs with the correct delimiter (often `;`).
   - Build a set of keys (CPFCNPJ) for each segment for O(1) membership checks.

5. **Compute the gap**
   - For each eligible record, check whether its key exists in the outreach set.
   - Group non-matches by the rule bucket (e.g., which days bucket).

6. **Report**
   - Quantify: eligible vs reached vs pending per segment and per bucket.
   - Show a sample of pending records (up to 10).
   - Cross-check "effective media" reported vs distinct contacts reached to detect duplicates or wasted sends.

7. **Export**
   - Optionally write the "not contacted" list to CSV for the next outreach cycle.

## Pitfalls

| Problem | Fix |
|---|---|
| Line-prefixed JSON file | Split each line on first `|` before parsing |
| Trailing non-JSON content | Slice string to last `]` or `}` |
| Numeric fields as strings | Try/except int coercion; skip invalid |
| Enum case/variations | Use `.strip().upper()` |
| Key formatting drift (dots/dashes) | Canonicalize CPF/CNPJ on both sides |

## References

See `references/outreach-gap-pattern.py` for a ready-to-adapt Python script covering JSON extraction (including line-prefix handling), field normalization, set-based diff, and reporting.