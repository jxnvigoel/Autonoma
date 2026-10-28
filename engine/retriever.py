"""
ID-based retrieval (Handbook 25.1-25.3).

Artifacts are split into items by ID (a heading section, a table row, a list entry or a
backlog story). A task receives exactly the items it cites (method 1) plus one hop of the
items those cite (method 2), within a character budget. When the budget is exceeded the
remaining items are sent as titles only, so the agent can ask for them by ID.
"""

import os
import re
import json
from typing import Dict, Iterable, List, Optional

ID_RE = re.compile(r"\b((?:FR|NFR|AC|API|TBL|ADR|ST|SLO|ROLE|TC|BUG|PT|REV|ASM|OQ|NG|F|J|S|P|Q|R|G|M|T)-\d{1,4})\b")
DOC_FILES = ["prd.md", "requirements.md", "architecture.md", "schema.md", "openapi.yaml", "app-flow.md",
             "design-brief.md", "feasibility.md", "readiness.md"]


def _norm(item_id: str) -> str:
    prefix, num = item_id.split("-", 1)
    return f"{prefix}-{int(num):03d}" if num.isdigit() else item_id


def _add(items: Dict[str, Dict[str, str]], item_id: str, text: str, source: str) -> None:
    key = _norm(item_id)
    text = text.strip()
    if not text:
        return
    existing = items.get(key)
    # Keep the most specific definition: prefer the shortest text that starts with the ID.
    if existing is None or (len(text) < len(existing["text"]) and item_id in text[:40]):
        items[key] = {"id": key, "text": text[:2000], "source": source}


def index_markdown(text: str, source: str, items: Dict[str, Dict[str, str]]) -> None:
    lines = text.splitlines()
    for i, line in enumerate(lines):
        stripped = line.strip()
        head = re.match(r"^(#{1,6})\s+(.*)$", stripped)
        if head:
            ids = ID_RE.findall(head.group(2))
            if ids:
                level = len(head.group(1))
                body = [line]
                for nxt in lines[i + 1:]:
                    m = re.match(r"^(#{1,6})\s", nxt.strip())
                    if m and len(m.group(1)) <= level:
                        break
                    body.append(nxt)
                _add(items, ids[0], "\n".join(body), source)
            continue
        if stripped.startswith("|"):
            cells = [c.strip(" `*[]") for c in stripped.strip("|").split("|")]
            if cells:
                first = ID_RE.search(cells[0])
                if first:
                    _add(items, first.group(1), stripped, source)
            continue
        bullet = re.match(r"^(?:[-*]|\d+\.)\s+(.*)$", stripped)
        if bullet:
            first = ID_RE.match(bullet.group(1).lstrip("`*[ "))
            if first:
                _add(items, first.group(1), stripped, source)


def index_project(docs_dir: str, qa_log: Optional[List[Dict[str, str]]] = None,
                  backlog: Optional[Dict[str, object]] = None) -> Dict[str, Dict[str, str]]:
    items: Dict[str, Dict[str, str]] = {}
    for name in DOC_FILES:
        path = os.path.join(docs_dir, name)
        if os.path.isfile(path):
            with open(path, "r", encoding="utf-8", errors="replace") as f:
                index_markdown(f.read(), f"docs/{name}", items)
    adr_dir = os.path.join(docs_dir, "adr")
    if os.path.isdir(adr_dir):
        for fn in sorted(os.listdir(adr_dir)):
            m = ID_RE.search(fn)
            if m:
                with open(os.path.join(adr_dir, fn), "r", encoding="utf-8", errors="replace") as f:
                    items[_norm(m.group(1))] = {"id": _norm(m.group(1)), "text": f.read()[:2000], "source": f"docs/adr/{fn}"}
    for q in qa_log or []:
        if q.get("id"):
            items[_norm(q["id"])] = {"id": _norm(q["id"]), "source": "qa_log.json",
                                     "text": f"{q['id']}: Q: {q.get('question', '')} A: {q.get('answer', '')}"}
    for st in (backlog or {}).get("stories", []) if isinstance(backlog, dict) else []:
        if st.get("id"):
            items[_norm(st["id"])] = {"id": _norm(st["id"]), "source": "docs/backlog.json",
                                      "text": json.dumps(st, indent=1)}
    return items


def retrieve(items: Dict[str, Dict[str, str]], ids: Iterable[str], budget_chars: int = 24000,
             follow_one_hop: bool = True) -> Dict[str, object]:
    wanted: List[str] = []
    for i in ids:
        k = _norm(i)
        if k not in wanted:
            wanted.append(k)
    missing = [i for i in wanted if i not in items]
    order = [i for i in wanted if i in items]
    if follow_one_hop:
        for i in list(order):
            for cited in ID_RE.findall(items[i]["text"]):
                k = _norm(cited)
                if k in items and k not in order:
                    order.append(k)
    parts, used, titles_only = [], 0, []
    for k in order:
        block = f"[{k}] ({items[k]['source']})\n{items[k]['text']}"
        if used + len(block) <= budget_chars:
            parts.append(block)
            used += len(block)
        else:
            titles_only.append(f"[{k}] {items[k]['text'].splitlines()[0][:120]}")
    text = "\n\n".join(parts)
    if titles_only:
        text += "\n\n# More items (titles only; ask with need_context)\n" + "\n".join(titles_only)
    return {"text": text, "included": order[:len(parts)], "titles_only": titles_only, "missing": missing}
