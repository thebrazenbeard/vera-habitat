"""Inspect workspace startup metadata and font headers without executing assets."""
from __future__ import annotations

import json
from pathlib import Path
import re
import unittest


ROOT = Path(__file__).resolve().parents[1]
STRING_OR_COMMENT = re.compile(r'("(?:\\.|[^"\\])*")|(/\*[\s\S]*?\*/|//[^\r\n]*)')
STRING_OR_TRAILING_COMMA = re.compile(r'("(?:\\.|[^"\\])*")|(,\s*(?=[}\]]))')
NODE = re.compile(r'(?i)(?:^|[/\\\s"\'])node(?:\.exe)?(?=$|[/\\\s"\'])')
FONT_EXTENSION = re.compile(r'(?i)\.(?:ttf|woff2?|eot|svg)(?:\b|$)')


def parse_jsonc(source: str) -> object:
    """Accept UTF-8 BOM, JSONC comments and trailing commas; retain quoted text."""
    source = source.lstrip("\ufeff")
    source = STRING_OR_COMMENT.sub(lambda match: match.group(1) or "", source)
    source = STRING_OR_TRAILING_COMMA.sub(lambda match: match.group(1) or "", source)
    return json.loads(source)


def scan(value: object, location: str = "root") -> list[str]:
    findings: list[str] = []
    if isinstance(value, list):
        for index, item in enumerate(value):
            findings.extend(scan(item, f"{location}[{index}]"))
    elif isinstance(value, dict):
        # VS Code allows command and arguments to be specified separately.
        command = value.get("command", "")
        arguments = value.get("args", [])
        combined = str(command) + " " + json.dumps(arguments, ensure_ascii=False)
        if isinstance(command, str) and NODE.search(combined) and FONT_EXTENSION.search(combined):
            findings.append(f"{location}: executable disguised as font (command+args)")
        for key, item in value.items():
            here = f"{location}.{key}"
            if key == "runOn" and item == "folderOpen":
                findings.append(f"{here}: automatic folderOpen task")
            if key == "task.allowAutomaticTasks" and item in (True, "on", "true", "always"):
                findings.append(f"{here}: automatic-task consent override")
            if key in ("command", "args", "windows", "linux", "osx"):
                serialized = json.dumps(item, ensure_ascii=False) if not isinstance(item, str) else item
                if NODE.search(serialized) and FONT_EXTENSION.search(serialized):
                    findings.append(f"{here}: executable disguised as font")
            findings.extend(scan(item, here))
    return findings


def font_error(path: Path) -> str | None:
    """Check sfnt directory bounds, not just a four-byte magic prefix."""
    data = path.read_bytes()
    if path.suffix.lower() == ".ttf":
        if len(data) < 12 or data[:4] not in (b"\x00\x01\x00\x00", b"OTTO", b"true", b"typ1"):
            return "missing sfnt header"
        n_tables = int.from_bytes(data[4:6], "big")
        if not (1 <= n_tables <= 4096) or 12 + 16 * n_tables > len(data):
            return "impossible sfnt table count"
        for index in range(n_tables):
            entry = 12 + 16 * index
            offset = int.from_bytes(data[entry + 8:entry + 12], "big")
            size = int.from_bytes(data[entry + 12:entry + 16], "big")
            if offset > len(data) or size > len(data) - offset:
                return "sfnt table outside file"
    elif path.suffix.lower() in (".woff", ".woff2"):
        expected = b"wOFF" if path.suffix.lower() == ".woff" else b"wOF2"
        if len(data) < 44 or data[:4] != expected:
            return "missing WOFF header"
        if int.from_bytes(data[8:12], "big") != len(data):
            return "invalid WOFF declared length"
    return None


class WorkspaceFontAutostartSafety(unittest.TestCase):
    def test_workspace_configurations_are_inert(self):
        paths = list(ROOT.rglob(".vscode/*.json")) + list(ROOT.rglob("*.code-workspace"))
        for path in paths:
            if ".git" in path.parts or ".venv" in path.parts:
                continue
            with self.subTest(path=str(path.relative_to(ROOT))):
                data = parse_jsonc(path.read_text(encoding="utf-8-sig"))
                self.assertFalse(scan(data), scan(data))

    def test_fonts_are_fonts(self):
        fonts = ROOT / "public" / "fonts"
        self.assertFalse((fonts / "fa-solid-600.ttf").exists(), "known counterfeit font")
        if fonts.exists():
            for path in fonts.iterdir():
                if path.suffix.lower() in (".ttf", ".woff", ".woff2"):
                    with self.subTest(path=path.name):
                        self.assertIsNone(font_error(path), f"{path}: {font_error(path)}")

    def test_no_concealed_script_ignore(self):
        ignore = ROOT / ".gitignore"
        if ignore.exists():
            self.assertNotRegex(ignore.read_text(encoding="utf-8"), r"(?im)^\s*/?config\.bat\s*$")

    def test_jsonc_bom_and_override_fixture_is_rejected(self):
        malicious = '\ufeff{ // comment\n "tasks": [{"runOptions": {"runOn": "folderOpen"},"windows": {"command":"node", "args":["./public/fonts/fa-solid-600.ttf"]},}], "settings":{"task.allowAutomaticTasks":true}}'
        findings = scan(parse_jsonc(malicious))
        self.assertTrue(any("folderOpen" in item for item in findings), findings)
        self.assertTrue(any("disguised" in item for item in findings), findings)
        self.assertTrue(any("consent" in item for item in findings), findings)

    def test_safe_fixture_does_not_false_positive(self):
        fixture = '{"tasks":[{"label":"Build","command":"python -m compileall src"}],"settings":{"task.allowAutomaticTasks":"off"}}'
        self.assertEqual(scan(parse_jsonc(fixture)), [])

    def test_split_command_and_args_is_rejected(self):
        task = {"command": "node", "args": ["./public/fonts/unknown.ttf"]}
        findings = scan(task)
        self.assertTrue(any("disguised" in item for item in findings), findings)


if __name__ == "__main__":
    unittest.main()
