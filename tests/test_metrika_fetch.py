"""Metrika fetch: query_error / CS_ERR_UNKNOWN → BLOCKER, no secret leak, no retry."""
from __future__ import annotations

import io
import json
import os
import subprocess
import sys
import tempfile
import unittest
import urllib.error
from pathlib import Path
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from scripts.excalibur_blog_metrika_fetch import (  # noqa: E402
    build_metrika_blocker,
    fetch_counter_preflight,
    is_query_error,
    is_unverified_code_status,
    parse_api_error_body,
    redact_metrika_secrets,
)

QUERY_ERROR_BODY = json.dumps(
    {
        "errors": [
            {
                "error_type": "query_error",
                "message": "Query is too complicated. Please reduce the date interval or sampling.",
            }
        ],
        "code": 400,
        "message": "Query is too complicated. Please reduce the date interval or sampling.",
    }
)
TOKEN = "test-oauth-not-real-token"
COUNTER = "99999999"


class _FakeHTTPError(urllib.error.HTTPError):
    def __init__(self, code: int, body: str) -> None:
        super().__init__(
            url="https://api-metrika.yandex.net/stat/v1/data",
            code=code,
            msg="Bad Request",
            hdrs=None,
            fp=io.BytesIO(body.encode("utf-8")),
        )


class _FakeResp:
    def __init__(self, body: str) -> None:
        self._body = body.encode("utf-8")

    def read(self) -> bytes:
        return self._body

    def __enter__(self) -> "_FakeResp":
        return self

    def __exit__(self, *args: object) -> bool:
        return False


class MetrikaClassifyTest(unittest.TestCase):
    def test_parse_query_error_json(self) -> None:
        parsed = parse_api_error_body(QUERY_ERROR_BODY)
        self.assertEqual(parsed["error_type"], "query_error")
        self.assertIn("too complicated", parsed["message"].lower())
        self.assertTrue(is_query_error(parsed["error_type"], parsed["message"], QUERY_ERROR_BODY))

    def test_query_error_plus_cs_err_unknown_blocker(self) -> None:
        payload = build_metrika_blocker(
            http_code=400,
            body=QUERY_ERROR_BODY,
            token=TOKEN,
            counter_id=COUNTER,
            code_status="CS_ERR_UNKNOWN",
            counter_status="Active",
            permission="own",
            source="reports",
        )
        self.assertEqual(payload["status"], "BLOCKER")
        self.assertEqual(payload["blocker"], "METRIKA FEEDBACK BLOCKER")
        self.assertEqual(payload["reason"], "query_error")
        self.assertTrue(payload["do_not_retry"])
        self.assertEqual(payload["code_status"], "CS_ERR_UNKNOWN")
        blob = json.dumps(payload)
        self.assertNotIn(TOKEN, blob)
        self.assertNotIn(COUNTER, blob)
        self.assertIn("Do not retry", " ".join(payload["do_not"]))
        self.assertTrue(payload["needed_human"])

    def test_redact_token_and_counter(self) -> None:
        raw = f"OAuth {TOKEN} counter={COUNTER} query_error"
        out = redact_metrika_secrets(raw, token=TOKEN, counter_id=COUNTER)
        self.assertNotIn(TOKEN, out)
        self.assertNotIn(COUNTER, out)

    def test_http_401_is_credentials_blocker(self) -> None:
        payload = build_metrika_blocker(
            http_code=401,
            body='{"message":"invalid token"}',
            token=TOKEN,
            counter_id=COUNTER,
            source="management",
        )
        self.assertEqual(payload["blocker"], "METRIKA CREDENTIALS BLOCKER")
        self.assertTrue(payload["do_not_retry"])
        self.assertFalse(is_unverified_code_status("CS_OK"))
        self.assertTrue(is_unverified_code_status("CS_ERR_UNKNOWN"))

    def test_preflight_omits_login_and_id(self) -> None:
        body = json.dumps(
            {
                "counter": {
                    "id": int(COUNTER),
                    "status": "Active",
                    "code_status": "CS_ERR_UNKNOWN",
                    "permission": "own",
                    "owner_login": "secret-login",
                    "site": "https://example.test",
                    "code": "<script>secret</script>",
                    "activity_status": "high",
                    "type": "simple",
                    "pro": 0,
                }
            }
        )

        def fake_urlopen(req: object, timeout: int = 60) -> _FakeResp:
            return _FakeResp(body)

        with patch("urllib.request.urlopen", fake_urlopen):
            meta = fetch_counter_preflight(TOKEN, COUNTER)
        self.assertEqual(meta["code_status"], "CS_ERR_UNKNOWN")
        self.assertEqual(meta["status"], "Active")
        dumped = json.dumps(meta)
        self.assertNotIn("secret-login", dumped)
        self.assertNotIn("script", dumped)
        self.assertNotIn("id", dumped)


class MetrikaMainPathTest(unittest.TestCase):
    def test_main_reports_query_error_json_blocker(self) -> None:
        from scripts import excalibur_blog_metrika_fetch as mf

        calls: list[str] = []

        def fake_urlopen(req: object, timeout: int = 60) -> _FakeResp:
            url = str(getattr(req, "full_url", req))
            calls.append(url)
            if "management/v1/counter" in url:
                return _FakeResp(
                    json.dumps(
                        {
                            "counter": {
                                "id": int(COUNTER),
                                "status": "Active",
                                "code_status": "CS_ERR_UNKNOWN",
                                "permission": "own",
                                "owner_login": "secret-login",
                                "activity_status": "high",
                                "type": "simple",
                                "pro": 0,
                            }
                        }
                    )
                )
            raise _FakeHTTPError(400, QUERY_ERROR_BODY)

        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            (root / "shared").mkdir()
            (root / "shared" / "published-articles.md").write_text(
                "| date | topic_id | slug | title | status |\n"
                "|------|----------|------|-------|--------|\n",
                encoding="utf-8",
            )
            env = {
                "YANDEX_METRIKA_OAUTH_TOKEN": TOKEN,
                "YANDEX_METRIKA_COUNTER_ID": COUNTER,
            }
            buf = io.StringIO()
            with patch.dict(os.environ, env, clear=False):
                with patch("urllib.request.urlopen", fake_urlopen):
                    with patch.object(sys, "argv", ["metrika", "--root", str(root), "--days", "30"]):
                        with patch.object(sys, "stdout", buf):
                            code = mf.main()
        self.assertEqual(code, 2)
        out = buf.getvalue()
        data = json.loads(out)
        self.assertEqual(data["status"], "BLOCKER")
        self.assertEqual(data["blocker"], "METRIKA FEEDBACK BLOCKER")
        self.assertTrue(data["do_not_retry"])
        self.assertEqual(data["reason"], "query_error")
        self.assertEqual(data["code_status"], "CS_ERR_UNKNOWN")
        self.assertNotIn(TOKEN, out)
        self.assertNotIn(COUNTER, out)
        self.assertNotIn("secret-login", out)
        self.assertTrue(any("management/v1/counter" in u for u in calls))
        self.assertTrue(any("stat/v1/data" in u for u in calls))

    def test_dry_run_ledger_no_api(self) -> None:
        proc = subprocess.run(
            [
                sys.executable,
                str(ROOT / "scripts" / "excalibur_blog_metrika_fetch.py"),
                "--dry-run-ledger",
                "--root",
                str(ROOT),
            ],
            check=False,
            capture_output=True,
            text=True,
        )
        self.assertEqual(proc.returncode, 0, proc.stderr)
        data = json.loads(proc.stdout)
        self.assertEqual(data["status"], "PASS")
        self.assertIn("ledger_slugs", data)

    def test_missing_env_blocker_json(self) -> None:
        env = os.environ.copy()
        env.pop("YANDEX_METRIKA_OAUTH_TOKEN", None)
        env.pop("YANDEX_METRIKA_COUNTER_ID", None)
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            (root / "shared").mkdir()
            (root / "shared" / "published-articles.md").write_text("", encoding="utf-8")
            proc = subprocess.run(
                [
                    sys.executable,
                    str(ROOT / "scripts" / "excalibur_blog_metrika_fetch.py"),
                    "--root",
                    str(root),
                    "--days",
                    "30",
                    "--ingest",
                ],
                check=False,
                capture_output=True,
                text=True,
                env=env,
                cwd=str(root),
            )
        self.assertEqual(proc.returncode, 2)
        data = json.loads(proc.stdout)
        self.assertEqual(data["status"], "BLOCKER")
        self.assertEqual(data["blocker"], "METRIKA CREDENTIALS BLOCKER")
        self.assertTrue(data["do_not_retry"])


class MetrikaLearnerContractTest(unittest.TestCase):
    def test_learner_still_requires_days_30_ingest(self) -> None:
        paths = [
            ROOT / "skills/content-learner-excalibur-blog/SKILL.md",
            ROOT / ".cursor/skills/content-learner-excalibur-blog/SKILL.md",
            ROOT / "shared/content-learning-contract.md",
        ]
        for path in paths:
            text = path.read_text(encoding="utf-8")
            self.assertIn("--days 30 --ingest", text, path)
            self.assertIn("CS_ERR_UNKNOWN", text, path)
            self.assertIn("do_not_retry", text, path)
            self.assertNotRegex(
                text,
                r"Метрика\s+\*\*необязательна\*\*|Metrika is optional",
            )


if __name__ == "__main__":
    unittest.main()
