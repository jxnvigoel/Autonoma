"""
Architecture model for the Architect's visuals: parsed by code from the documents the Architect wrote
(architecture.md, schema.md, openapi.yaml, ADRs, prd.md). Nothing here is generated or guessed: every
node, table, link and endpoint comes from a line in those files, so the pictures match the documents.
"""

import os
import re
from typing import Any, Dict, List, Optional

import yaml

ID_RE = re.compile(r"\b(?:F|FR|NFR|ADR|API|TBL|ROLE|Q)-\d{2,3}\b")


def _read(path: str) -> str:
    return open(path, "r", encoding="utf-8").read() if os.path.exists(path) else ""


def _section(md: str, number: int) -> str:
    m = re.search(rf"^##\s+{number}\.\s.*?$(.*?)(?=^##\s+\d+\.|\Z)", md, re.M | re.S)
    return m.group(1) if m else ""


def _table_rows(text: str) -> List[List[str]]:
    rows = []
    for line in text.splitlines():
        line = line.strip()
        if not line.startswith("|") or re.match(r"^\|\s*:?-{2,}", line):
            continue
        cells = [c.strip() for c in line.strip("|").split("|")]
        rows.append(cells)
    return rows[1:] if rows else []  # drop the header row


def _plain(cell: str) -> str:
    return re.sub(r"[*`]", "", cell).strip()


def parse_mermaid_flowchart(md: str) -> Dict[str, Any]:
    """Nodes, groups (subgraphs) and edges of the first ```mermaid flowchart in the document."""
    m = re.search(r"```mermaid\s*\n(.*?)```", md, re.S)
    if not m or not re.match(r"\s*(flowchart|graph)\b", m.group(1)):
        return {"direction": "TD", "nodes": [], "groups": [], "edges": []}
    lines = m.group(1).splitlines()
    direction = (re.match(r"\s*(?:flowchart|graph)\s+(\w+)", lines[0]) or [None, "TD"])[1]
    nodes: Dict[str, Dict[str, Any]] = {}
    groups: List[Dict[str, Any]] = []
    stack: List[str] = []
    edges: List[Dict[str, Any]] = []
    shape_re = re.compile(r"([A-Za-z0-9_]+)\s*(\[\(.*?\)\]|\(\(.*?\)\)|\[\[.*?\]\]|\[.*?\]|\(.*?\)|\{.*?\})")

    def node(token: str) -> Optional[str]:
        token = token.strip()
        sm = shape_re.fullmatch(token)
        nid = sm.group(1) if sm else (token if re.fullmatch(r"[A-Za-z0-9_]+", token) else None)
        if not nid:
            return None
        if nid not in nodes:
            nodes[nid] = {"id": nid, "label": nid, "kind": "service", "group": stack[-1] if stack else None}
        if sm:
            raw = sm.group(2)
            kind = "database" if raw.startswith("[(") else "decision" if raw.startswith("{") else "service"
            label = re.sub(r"<br\s*/?>", "\n", raw.strip("[](){}")).strip('"')
            nodes[nid].update({"label": label, "kind": kind})
        return nid

    for raw in lines[1:]:
        line = raw.strip()
        if not line or line.startswith("%%"):
            continue
        sg = re.match(r"subgraph\s+([A-Za-z0-9_]+)\s*(?:\[(.*?)\])?", line)
        if sg:
            gid = sg.group(1)
            groups.append({"id": gid, "label": sg.group(2) or gid, "parent": stack[-1] if stack else None})
            stack.append(gid)
            continue
        if line == "end":
            stack.pop() if stack else None
            continue
        parts = re.split(r"\s*(--\s*[^->]+?\s*-->|-->\|[^|]*\||-->|-\.->|==>|---)\s*", line)
        if len(parts) >= 3:
            prev = node(parts[0])
            for i in range(1, len(parts) - 1, 2):
                arrow, target = parts[i], node(parts[i + 1])
                lab = re.match(r"--\s*(.+?)\s*-->", arrow) or re.match(r"-->\|(.*)\|", arrow)
                if prev and target:
                    edges.append({"from": prev, "to": target, "label": lab.group(1).strip() if lab else ""})
                prev = target
        else:
            node(line)
    return {"direction": direction, "nodes": list(nodes.values()), "groups": groups, "edges": edges}


def parse_schema(schema_md: str) -> List[Dict[str, Any]]:
    """Tables, columns, primary and foreign keys from the CREATE TABLE statements in schema.md."""
    ids = {m.group(2): m.group(1) for m in re.finditer(r"(TBL-\d+)\**\s*`(\w+)`", schema_md)}
    tables = []
    for m in re.finditer(r"CREATE TABLE(?: IF NOT EXISTS)?\s+[`\"]?(\w+)[`\"]?\s*\((.*?)\n\);", schema_md, re.S | re.I):
        name, body = m.group(1), m.group(2)
        cols, fks = [], []
        for line in body.splitlines():
            line = re.sub(r"--.*$", "", line).strip().rstrip(",")
            if not line:
                continue
            fk = re.match(r"FOREIGN KEY\s*\((\w+)\)\s*REFERENCES\s+(\w+)\s*\((\w+)\)", line, re.I)
            if fk:
                fks.append({"column": fk.group(1), "table": fk.group(2), "ref_column": fk.group(3)})
                continue
            if re.match(r"(PRIMARY KEY|UNIQUE|CHECK|CONSTRAINT)\b", line, re.I):
                continue
            cm = re.match(r"[`\"]?(\w+)[`\"]?\s+(\w+)(.*)", line)
            if cm:
                rest = cm.group(3)
                inline_fk = re.search(r"REFERENCES\s+(\w+)\s*\((\w+)\)", rest, re.I)
                if inline_fk:
                    fks.append({"column": cm.group(1), "table": inline_fk.group(1), "ref_column": inline_fk.group(2)})
                cols.append({"name": cm.group(1), "type": cm.group(2).upper(),
                             "pk": "PRIMARY KEY" in rest.upper(), "nullable": "NOT NULL" not in rest.upper(),
                             "unique": "UNIQUE" in rest.upper()})
        fk_cols = {f["column"] for f in fks}
        for c in cols:
            c["fk"] = c["name"] in fk_cols
        tables.append({"name": name, "id": ids.get(name), "columns": cols, "foreign_keys": fks})
    return tables


def parse_openapi(text: str) -> List[Dict[str, Any]]:
    try:
        spec = yaml.safe_load(text) or {}
    except yaml.YAMLError:
        return []
    out = []
    for path, ops in (spec.get("paths") or {}).items():
        for method, op in (ops or {}).items():
            if method.lower() not in ("get", "post", "put", "patch", "delete") or not isinstance(op, dict):
                continue
            summary = op.get("summary") or ""
            refs = ID_RE.findall(f"{summary} {op.get('description') or ''} {op.get('operationId') or ''}")
            out.append({"method": method.upper(), "path": path, "summary": re.sub(r"\[[^\]]+\]\s*", "", summary).strip(),
                        "features": sorted({r for r in refs if r.startswith("F-")}),
                        "api_id": next((r for r in refs if r.startswith("API-")), None),
                        "auth": bool(op.get("security", spec.get("security")))})
    return out


def parse_features(prd_md: str) -> List[Dict[str, Any]]:
    feats = []
    for row in _table_rows(_section(prd_md, 5)):
        if len(row) >= 4 and re.fullmatch(r"F-\d{3}", _plain(row[0])):
            feats.append({"id": _plain(row[0]), "name": _plain(row[1]), "priority": _plain(row[3])})
    return feats


def parse_adrs(adr_dir: str) -> List[Dict[str, Any]]:
    out = []
    if not os.path.isdir(adr_dir):
        return out
    for fn in sorted(os.listdir(adr_dir)):
        text = _read(os.path.join(adr_dir, fn))
        title = re.search(r"^#\s+(ADR-\d+):\s*(.+)$", text, re.M)
        status = re.search(r"\*\*Status\*\*:\s*(\w+)", text)
        decision = re.search(r"^##\s+Decision\s*\n+(.+?)(?:\n\n|\Z)", text, re.M | re.S)
        out.append({"id": title.group(1) if title else fn[:-3], "title": title.group(2).strip() if title else fn,
                    "status": status.group(1) if status else None,
                    "decision": re.sub(r"\s+", " ", decision.group(1)).strip()[:400] if decision else None,
                    "driven_by": ID_RE.findall((re.search(r"\*\*Driven by\*\*:(.*)", text) or [None, ""])[1])})
    return out


def build_model(project_dir: str) -> Dict[str, Any]:
    docs = os.path.join(project_dir, "docs")
    arch = _read(os.path.join(docs, "architecture.md"))
    endpoints = parse_openapi(_read(os.path.join(docs, "openapi.yaml")))
    features = parse_features(_read(os.path.join(docs, "prd.md")))
    per_feature = {f["id"]: 0 for f in features}
    for ep in endpoints:
        for fid in ep["features"]:
            per_feature[fid] = per_feature.get(fid, 0) + 1
    stack = [{"layer": _plain(r[0]), "choice": _plain(r[1]), "refs": ID_RE.findall(r[-1])}
             for r in _table_rows(_section(arch, 3)) if len(r) >= 2]
    slices = []
    for m in re.finditer(r"^\s*\d+\.\s+\*\*(.+?)\*\*:?\s*$(.*?)(?=^\s*\d+\.\s+\*\*|\Z)", _section(arch, 11), re.M | re.S):
        body = m.group(2)
        slices.append({"title": m.group(1).strip().rstrip(":"),
                       "items": [re.sub(r"\s+", " ", i).strip() for i in re.findall(r"^\s*-\s+(.+)$", body, re.M)],
                       "refs": sorted(set(ID_RE.findall(body)))})
    seats = [{"seat": _plain(r[0]), "role": _plain(r[1]), "count": _plain(r[2]), "refs": ID_RE.findall(r[-1])}
             for r in _table_rows(_section(arch, 12)) if len(r) >= 3]
    pattern = re.search(r"\*\*Pattern:\*\*\s*(.+)", _section(arch, 4))
    return {
        "has_architecture": bool(arch),
        "pattern": pattern.group(1).strip() if pattern else None,
        "system": parse_mermaid_flowchart(_section(arch, 4) or arch),
        "stack": stack,
        "tables": parse_schema(_read(os.path.join(docs, "schema.md"))),
        "endpoints": endpoints,
        "features": features,
        "endpoints_per_feature": [{"feature": k, "count": v} for k, v in sorted(per_feature.items())],
        "uncovered_features": sorted(k for k, v in per_feature.items() if v == 0),
        "adrs": parse_adrs(os.path.join(docs, "adr")),
        "build_slices": slices,
        "team": seats,
    }
