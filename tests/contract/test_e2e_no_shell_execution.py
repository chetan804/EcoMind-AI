"""The browser tests must never run a command taken from configuration (security finding, 2026-10-21).

Earlier, tests/e2e/specs/mail.ts ran the shell command in an environment variable to read the e-mail log.
The helper now reads Mailpit's REST API or a log file directly. This guard keeps it that way: no
child-process use anywhere under tests/e2e, and the retired variable is mentioned only by the one test that
proves it is ignored.
"""

from __future__ import annotations

import re
import subprocess
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
RETIRED = "E2E_MAIL_LOG_COMMAND"
ALLOWED_TO_MENTION = {"tests/e2e/specs/mail.unit.spec.ts", "tests/contract/test_e2e_no_shell_execution.py"}
PROCESS_USE = re.compile(r"child_process|\bexecSync\b|\bexecFileSync\b|\bspawnSync\b|\bspawn\(|\bexec\(")


def tracked() -> list[str]:
    out = subprocess.run(["git", "ls-files"], cwd=ROOT, check=True, capture_output=True, text=True).stdout
    return [line for line in out.splitlines() if (ROOT / line).is_file()]


def test_no_browser_test_file_uses_child_processes() -> None:
    offenders = []
    for name in tracked():
        if not name.startswith("tests/e2e/") or not name.endswith((".ts", ".mjs", ".js", ".mts", ".cts")):
            continue
        text = (ROOT / name).read_text(encoding="utf-8")
        if PROCESS_USE.search(text):
            offenders.append(name)
    assert offenders == []


def test_the_retired_command_variable_is_gone_everywhere() -> None:
    mentions = []
    for name in tracked():
        try:
            text = (ROOT / name).read_text(encoding="utf-8")
        except UnicodeDecodeError:
            continue
        if RETIRED in text and name not in ALLOWED_TO_MENTION:
            mentions.append(name)
    assert mentions == []


def test_the_ci_pipeline_uses_the_mailpit_api() -> None:
    workflow = (ROOT / ".github/workflows/quality-gates.yml").read_text(encoding="utf-8")
    assert "E2E_MAILPIT_URL" in workflow
    assert "E2E_MAIL_LOG" not in workflow
