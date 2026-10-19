import os
import sys
import json
sys.path.append(os.path.join(os.path.dirname(__file__), ".."))
from engine.judge import evaluate_architecture_with_judge

broken_arch_text = """# Technical Requirements Document & System Architecture: BrokenApp

## 1. Constraints that shape the design
| NFR | Target | Design Impact |
|---|---|---|
| [NFR-01] | Search response time under 1.0 s | Fast queries |
<!-- Note: NFR-02, NFR-03, NFR-04, NFR-05 are completely missing -->

## 2. Capacity estimate
The system will handle 100,000 requests per second effortlessly. Storage is x.
<!-- No arithmetic, no Little's Law, placeholder 'is x' -->

## 3. Tech stack
We will deploy a Microservices Architecture with a multi-node Kafka event stream and a distributed Redis cluster.
We also enable high-frequency algorithmic trading capabilities [Q-001].

## 4. Architecture overview
Standard components.

## 5. Authentication and authorization
Basic auth.

## 6. API
| ID | Method + Path | Feature | Auth Rule | Errors |
|---|---|---|---|---|
| API-001 | GET /items | [F-001] | None | 200 |

## 7. Data model
Tables defined elsewhere.

## 8. External integrations
None.

## 10. Reliability and operations
Standard uptime.
<!-- Missing Section 9 Security STRIDE and Section 11 Build Order Walking Skeleton -->
"""

mock_parsed_ba = {
    "app_name": "BrokenApp",
    "timeline": "6 weeks",
    "budget": "$10,000",
    "qa_map": {
        "Q-001": {
            "id": "Q-001",
            "question": "What is the tool?",
            "answer": "A local inspection tool for site engineers."
        }
    },
    "non_functional_reqs": [
        {"id": "NFR-01", "name": "Search Latency", "target": "< 1.0 s"},
        {"id": "NFR-02", "name": "Data Privacy", "target": "100% local"},
        {"id": "NFR-03", "name": "Local Capacity", "target": "3,000 records"},
        {"id": "NFR-04", "name": "Platform", "target": "macOS Desktop"},
        {"id": "NFR-05", "name": "Accessibility", "target": "WCAG 2.2 AA"}
    ],
    "functional_reqs": [
        {"id": "FR-01", "feature": "Deficiency Tagging", "priority": "Must"},
        {"id": "FR-02", "feature": "Punchlist Export", "priority": "Must"}
    ]
}

mock_prd_text = """
# Product Requirement Document: BrokenApp
## 5. Features
- F-001: Deficiency Tagging
- F-002: Punchlist Export
## 6. Non-functional requirements
- [NFR-01] Search Latency
- [NFR-02] Data Privacy
- [NFR-03] Local Capacity
- [NFR-04] Platform
- [NFR-05] Accessibility
"""

verdict = evaluate_architecture_with_judge(
    arch_text=broken_arch_text,
    prd_text=mock_prd_text,
    parsed_ba=mock_parsed_ba,
    rubric_path="skills/architect/rubric.json"
)

print("=== JUDGE VERDICT ON BROKEN ARCHITECTURE ===")
print(f"Pass: {verdict.get('pass')}")
print(f"Total Score: {verdict.get('total')}/{verdict.get('max')}")
print(f"Summary: {verdict.get('verdict_summary')}")
print(f"Unsupported Claims Count: {len(verdict.get('unsupported_claims', []))}")
print(json.dumps(verdict, indent=2))

assert verdict.get("pass") is False, "Judge must FAIL broken architecture document!"
assert len(verdict.get("unsupported_claims", [])) >= 5, "Judge must detect multiple fatal defects!"
print("\n>>> PROOF SUCCESSFUL: Judge correctly FAILED the broken architecture document!")
