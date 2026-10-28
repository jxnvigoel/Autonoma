#!/usr/bin/env python3
"""
scripts/check_citations.py

Verifies that every quoted handbook line in:
- docs/agents/*.md
- skills/*/role.md
- code comments in engine/*.py

exists verbatim in docs/handbook/VirtualOffice_Complete_Guide.md.
Also verifies that none of the forbidden invented phrases exist in the repo.
"""

import os
import sys
import re
from typing import List, Tuple, Dict, Any

HANDBOOK_PATH = "docs/handbook/VirtualOffice_Complete_Guide.md"

FORBIDDEN_PHRASES = [
    "Arithmetic is code, reason is LLM",
    "MissingInputError",
    "Table 6.1.3: Document roles get NO shell",
    "Document roles get NO shell",
    "Every downgrade must be logged with quality impact statement",
    "deterministic config pool",
    "Gate 2 sign-off: Client reviews",
    "Table 6.1.3",
]


def normalize_text(s: str) -> str:
    """Normalize quotes, hyphens, and whitespace for robust verbatim comparison."""
    s = s.replace("“", '"').replace("”", '"').replace("‘", "'").replace("’", "'")
    s = s.replace("—", "-").replace("–", "-")
    s = re.sub(r"\s+", " ", s)
    return s.strip()


def load_handbook(path: str = HANDBOOK_PATH) -> str:
    if not os.path.exists(path):
        raise FileNotFoundError(f"Handbook not found at {path}")
    with open(path, "r", encoding="utf-8") as f:
        return normalize_text(f.read())


def check_forbidden_phrases() -> List[str]:
    """Scan codebase for forbidden invented phrases."""
    errors = []
    root_dirs = ["docs", "skills", "engine", "tests"]
    for rd in root_dirs:
        if not os.path.exists(rd):
            continue
        for root, _, files in os.walk(rd):
            for f in files:
                if f.endswith((".py", ".md", ".json")):
                    fpath = os.path.join(root, f)
                    try:
                        with open(fpath, "r", encoding="utf-8", errors="ignore") as fh:
                            content = fh.read()
                        for phrase in FORBIDDEN_PHRASES:
                            if phrase.lower() in content.lower():
                                errors.append(f"Forbidden phrase found in {fpath}: '{phrase}'")
                    except Exception as e:
                        pass
    return errors


def extract_quotes_from_markdown(fpath: str) -> List[Tuple[int, str]]:
    """
    Extracts quoted phrases from markdown text, ignoring code blocks, inline code,
    and JSON snippets.
    """
    quotes = []
    with open(fpath, "r", encoding="utf-8") as f:
        lines = f.readlines()

    in_code_block = False
    for line_idx, line in enumerate(lines, start=1):
        stripped = line.strip()
        if stripped.startswith("```"):
            in_code_block = not in_code_block
            continue
        if in_code_block:
            continue

        # Strip inline code `...`
        clean_line = re.sub(r"`[^`]+`", "", line)

        # Skip json-like lines: "key": "value"
        if re.search(r'^\s*"[^"]+"\s*:', clean_line):
            continue

        # Match double-quoted phrases of >= 3 words or cited handbook phrases
        for m in re.finditer(r'["“]([^"”\n\r]{10,})["”]', clean_line):
            q = m.group(1).strip()
            # Ignore markdown link syntax or purely code symbols
            if q.startswith("http") or q.startswith("/") or q.startswith("{") or q.endswith("}"):
                continue
            # If quote has at least 2 spaces (3 words) or is a known quoted term
            if " " in q:
                quotes.append((line_idx, q))

        # Check blockquotes citing handbook: > "..."
        if stripped.startswith(">"):
            bq_text = re.sub(r"^>\s*", "", stripped)
            bq_clean = re.sub(r'["“”]', "", bq_text).strip()
            if len(bq_clean) > 15 and " " in bq_clean:
                quotes.append((line_idx, bq_clean))

    return quotes


def extract_quotes_from_python_comments(fpath: str) -> List[Tuple[int, str]]:
    """Extracts quoted handbook citations from python comments."""
    quotes = []
    with open(fpath, "r", encoding="utf-8") as f:
        lines = f.readlines()

    for line_idx, line in enumerate(lines, start=1):
        if "#" not in line:
            continue
        comment_part = line.split("#", 1)[1].strip()
        # Look for quoted strings in comments that cite Handbook or rules
        if any(kw in comment_part.lower() for kw in ["handbook", "quote", "rule", "section"]):
            for m in re.finditer(r'["“]([^"”\n\r]{10,})["”]', comment_part):
                q = m.group(1).strip()
                if " " in q:
                    quotes.append((line_idx, q))
    return quotes


def main():
    print("=" * 70)
    print("RUNNING CITATION & VERBATIM HANDBOOK CHECKER (scripts/check_citations.py)")
    print("=" * 70)

    # 1. Load normalized handbook
    hb_norm = load_handbook(HANDBOOK_PATH)
    hb_lower = hb_norm.lower()
    print(f"Loaded handbook from {HANDBOOK_PATH} ({len(hb_norm)} chars normalized).")

    # 2. Check forbidden phrases
    forbidden_errors = check_forbidden_phrases()
    if forbidden_errors:
        print("\n[FAIL] Found forbidden invented phrases:")
        for err in forbidden_errors:
            print(f"  - {err}")
    else:
        print("\n[PASS] No forbidden invented phrases found in codebase.")

    # 3. Gather target files
    target_files = []
    # docs/agents/*.md
    if os.path.exists("docs/agents"):
        for f in os.listdir("docs/agents"):
            if f.endswith(".md"):
                target_files.append(("md", os.path.join("docs/agents", f)))
    # skills/*/role.md
    if os.path.exists("skills"):
        for root, _, files in os.walk("skills"):
            for f in files:
                if f == "role.md":
                    target_files.append(("md", os.path.join(root, f)))
    # engine/*.py
    if os.path.exists("engine"):
        for f in os.listdir("engine"):
            if f.endswith(".py"):
                target_files.append(("py", os.path.join("engine", f)))

    citation_failures = []
    verified_quotes_count = 0

    for ftype, fpath in sorted(target_files):
        if ftype == "md":
            extracted = extract_quotes_from_markdown(fpath)
        else:
            extracted = extract_quotes_from_python_comments(fpath)

        for line_no, quote_str in extracted:
            q_norm = normalize_text(quote_str)
            # Remove trailing punctuation for lenient prefix matching if sentence was punctuated
            q_clean = q_norm.strip(".,;:!? ")
            if len(q_clean) < 8:
                continue

            if q_clean.lower() in hb_lower:
                verified_quotes_count += 1
            else:
                # Double check with punctuation preserved
                if q_norm.lower() in hb_lower:
                    verified_quotes_count += 1
                else:
                    citation_failures.append((fpath, line_no, quote_str))

    print(f"\nChecked {len(target_files)} files: Verified {verified_quotes_count} verbatim Handbook quotes.")

    if citation_failures:
        print(f"\n[FAIL] Found {len(citation_failures)} ungrounded quotes not found verbatim in handbook:")
        for fp, lno, q in citation_failures:
            print(f"  - {fp}:{lno} -> \"{q}\"")

    total_failures = len(forbidden_errors) + len(citation_failures)
    if total_failures > 0:
        print(f"\nFAILED: Total citation errors: {total_failures}")
        sys.exit(1)
    else:
        print("\n[PASS] All cited handbook lines exist VERBATIM in docs/handbook/VirtualOffice_Complete_Guide.md!")
        sys.exit(0)


if __name__ == "__main__":
    main()
