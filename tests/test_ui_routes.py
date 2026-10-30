"""Every engine call the UI makes must hit a real engine route with the right method (no dead buttons)."""

import glob
import os
import re
import sys
import unittest

ROOT = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..")
sys.path.insert(0, os.path.join(ROOT, "engine"))

import main  # noqa: E402


def engine_routes():
    out = set()
    for r in main.app.routes:
        for m in getattr(r, "methods", None) or []:
            out.add((m, re.sub(r"\{[^}]+\}", "{}", r.path)))
    return out


def ui_calls():
    calls = []
    for f in glob.glob(os.path.join(ROOT, "src", "**", "*.ts*"), recursive=True):
        text = open(f, encoding="utf-8").read()
        # fetch(`${ENGINE_BASE_URL}/x/${id}`, { method: "POST" })
        for m in re.finditer(r"fetch\(\s*`\$\{ENGINE_BASE_URL\}([^`]*)`(.{0,300})", text, re.S):
            rest = m.group(2).split("fetch(")[0]
            meth = re.search(r'method:\s*"(\w+)"', rest)
            calls.append((f, m.group(1), meth.group(1) if meth else "GET"))
        # engineJson<...>(`/x/${id}`, postJson(...) | { method: "PUT" })
        for m in re.finditer(r"engineJson<(?:[^<>]|<[^<>]*>)*>\(\s*`([^`]*)`(.{0,200})", text, re.S):
            rest = m.group(2).split(";")[0]
            meth = re.search(r'method:\s*"(\w+)"', rest)
            calls.append((f, m.group(1), "POST" if "postJson(" in rest else meth.group(1) if meth else "GET"))
    return calls


class UiRoutesTest(unittest.TestCase):
    def test_every_ui_call_has_an_engine_route(self):
        routes = engine_routes()
        calls = [(f, p, m) for f, p, m in ui_calls() if not p.startswith("${")]  # generic helpers take a path
        self.assertGreater(len(calls), 40)  # the scan itself works
        missing = []
        for f, path, meth in calls:
            norm = re.sub(r"\$\{[^}]+\}", "{}", path.split("?")[0]).rstrip("/") or "/"
            if (meth, norm) not in routes:
                missing.append(f"{meth} {norm}  <- {os.path.relpath(f, ROOT)}")
        self.assertEqual(missing, [])


if __name__ == "__main__":
    unittest.main()
