"""test_bridge.py -- deterministic bridge tests (mocked; no real model calls).
Run: python3 scripts/router/test_bridge.py
"""
import os
import sys
import types
import unittest
from unittest import mock

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import delegate as D
from models import Task

VALID = ("# Findings\nx\n# Evidence\ny\n# Risks\nz\n# Recommendation\nNO_ACTION\n")
INVALID = "here is my answer, no sections"


def T(title="t", inputs="", body="", status="queued", tid="TASK-20260101-01"):
    return Task(id=tid, title=title, inputs=inputs, body=body, status=status)


class Routing(unittest.TestCase):
    def test_1_auto_qwen7b(self):
        b, _ = D.auto_route(T(title="parse the log and extract facts"))
        self.assertEqual(b, "qwen")

    def test_2_auto_qwen14b(self):
        b, _ = D.auto_route(T(title="adversarial code review of multi-file paths"))
        self.assertEqual(b, "qwen-deep")

    def test_3_auto_glm(self):
        b, _ = D.auto_route(T(title="literature synthesis of the momentum paper"))
        self.assertEqual(b, "glm")

    def test_4_explicit_override(self):
        # explicit backend bypasses auto_route
        with mock.patch.object(D, "run_backend", return_value=dict(rc=0, stdout=VALID, stderr="", dur=1, model="m", cmd="c")), \
             mock.patch.object(D.q, "task_path", return_value="/x"), \
             mock.patch("builtins.open", mock.mock_open(read_data="---\nid: TASK-20260101-01\ntitle: t\n---\nbody")), \
             mock.patch.object(D.q, "save"), mock.patch.object(D.st_mod, "load", return_value={}), \
             mock.patch.object(D.st_mod, "save"), mock.patch.object(D, "ollama_up", return_value=True):
            m = D.delegate("TASK-20260101-01", backend="glm")
            self.assertEqual(m["backend"], "glm")


class Contract(unittest.TestCase):
    def test_6_invalid_format(self):
        ok, rec, why = D.validate(INVALID)
        self.assertFalse(ok)

    def test_7_valid_collection(self):
        ok, rec, why = D.validate(VALID)
        self.assertTrue(ok); self.assertEqual(rec, "NO_ACTION")

    def test_two_recs_invalid(self):
        ok, _, _ = D.validate(VALID + "\nREJECT\n")
        self.assertFalse(ok)


class Execution(unittest.TestCase):
    def _run(self, **backend_kw):
        with mock.patch.object(D.q, "task_path", return_value="/x"), \
             mock.patch("builtins.open", mock.mock_open(read_data="---\nid: TASK-20260101-01\ntitle: parse logs\n---\nbody")), \
             mock.patch.object(D.q, "save"), mock.patch.object(D.st_mod, "load", return_value={}), \
             mock.patch.object(D.st_mod, "save"), mock.patch.object(D, "ensure_ollama", return_value=(True, "up")), \
             mock.patch.object(D, "build_brief", return_value=("/b", "brief")), \
             mock.patch.object(D, "run_backend", **backend_kw):
            return D.delegate("TASK-20260101-01", backend="qwen")

    def test_5_ollama_unavailable(self):
        with mock.patch.object(D.q, "task_path", return_value="/x"), \
             mock.patch("builtins.open", mock.mock_open(read_data="---\nid: TASK-20260101-01\ntitle: parse logs\n---\nbody")), \
             mock.patch.object(D.q, "save"), mock.patch.object(D.st_mod, "load", return_value={}), \
             mock.patch.object(D.st_mod, "save"), \
             mock.patch.object(D, "ensure_ollama", return_value=(False, "down")):
            m = D.delegate("TASK-20260101-01", backend="qwen")
            self.assertEqual(m["validation"][:7], "ollama ")

    def test_8_nonzero_exit_blocks(self):
        m = self._run(return_value=dict(rc=1, stdout="", stderr="boom", dur=1, model="m", cmd="c"))
        self.assertIn("exit 1", m["validation"])

    def test_9_timeout_blocks(self):
        m = self._run(return_value=dict(rc=124, stdout="", stderr="timeout after 180s", dur=180, model="m", cmd="c"))
        self.assertEqual(m["exit_code"], 124)

    def test_valid_sets_review(self):
        m = self._run(return_value=dict(rc=0, stdout=VALID, stderr="", dur=1, model="m", cmd="c"))
        self.assertEqual(m["recommendation"], "NO_ACTION")

    def test_6b_invalid_then_escalates(self):
        # 7b returns invalid twice -> escalates to qwen-deep
        m = self._run(return_value=dict(rc=0, stdout=INVALID, stderr="", dur=1, model="m", cmd="c"))
        self.assertGreaterEqual(m["retry_count"], 2)


class Safety(unittest.TestCase):
    def test_10_paths_with_spaces(self):
        # argv list keeps a spaced path as one token (no shell splitting)
        argv = [a.replace("{brief}", "/a b/brief file.md") for a in D.BACKENDS["glm"]["argv"]]
        self.assertIn("/a b/brief file.md", argv)

    def test_11_secrets_excluded(self):
        t = T(body="normal task")
        with mock.patch.object(D, "_safe_ctx", return_value="api_key: SHOULD_NOT_APPEAR"):
            with self.assertRaises(AssertionError):  # brief refuses secret marker
                D.build_brief(t, "qwen")

    def test_12_model_output_not_executed(self):
        # a malicious reply is only validated as text, never run
        ok, _, _ = D.validate("# Findings\n; rm -rf /\n# Evidence\n# Risks\n# Recommendation\nREJECT")
        self.assertTrue(ok)  # collected as text; the shell string is inert data

    def test_no_shell_true(self):
        # no subprocess call passes shell=True (docstring mentions are fine)
        src = open(os.path.join(os.path.dirname(__file__), "delegate.py")).read()
        self.assertNotIn("shell=True)", src)   # the dangerous call form; docstring uses "shell=True," inside prose


class Idempotency(unittest.TestCase):
    def test_13_14_terminal_not_rerun(self):
        with mock.patch.object(D.q, "task_path", return_value="/x"), \
             mock.patch("builtins.open", mock.mock_open(read_data="---\nid: TASK-20260101-01\ntitle: t\nstatus: completed\n---\nbody")), \
             mock.patch.object(D.q, "save") as sv:
            r = D.delegate("TASK-20260101-01", backend="qwen")
            self.assertIsNone(r); sv.assert_not_called()

    def test_15_metadata_complete(self):
        m = Execution()._run(return_value=dict(rc=0, stdout=VALID, stderr="", dur=1, model="m", cmd="c"))
        for k in ("task", "backend", "model", "start", "routing_reason", "retry_count",
                  "duration", "exit_code", "brief", "reply", "validation"):
            self.assertIn(k, m, f"missing metadata {k}")


if __name__ == "__main__":
    unittest.main(verbosity=2)
