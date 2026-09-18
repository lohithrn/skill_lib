"""
Tests for architecture_lint.py — the deterministic coding-rules pre-pass.

Covered:
  - file length, method length, and loop-body thresholds (SKILL.md rules 3/4/5)
  - vague file, folder, and method names (rules 1/2/7F)
  - single-member enum detection, and that multi-member enums are allowed (rule 7A)
  - module-level mutable globals vs. UPPER_CASE constants (rule 21)
  - target discovery: explicit paths, directory expansion, skip dirs

Run:  python3 scripts/test_architecture_lint.py

Stdlib `unittest` only, on purpose: a test that needs a package installed cannot
run on an offline machine, and this suite is the only proof the thresholds below
still match the prose.
"""

import tempfile
import unittest
from pathlib import Path

import architecture_lint as lint


def rules_for(findings) -> set[str]:
    return {f.rule for f in findings}


def write(path: Path, body: str) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(body)
    return path


class ArchitectureLintTest(unittest.TestCase):
    """One throwaway tree per test, so no test can see another's fixtures."""

    def setUp(self) -> None:
        temp = tempfile.TemporaryDirectory()
        self.addCleanup(temp.cleanup)
        self.tmp_path = Path(temp.name)

    # ----------------------------------------------------------------------- #
    # File length
    # ----------------------------------------------------------------------- #
    def test_file_over_250_lines_is_flagged(self):
        f = write(self.tmp_path / "big.py", "\n".join(f"x = {i}" for i in range(300)))
        assert "file-too-long" in rules_for(lint.scan_file(f))

    def test_short_file_is_not_flagged_for_length(self):
        f = write(self.tmp_path / "small.py", "x = 1\n")
        assert "file-too-long" not in rules_for(lint.scan_file(f))

    # ----------------------------------------------------------------------- #
    # Method / loop size
    # ----------------------------------------------------------------------- #
    def test_method_over_25_lines_is_flagged(self):
        body = "\n".join(f"    a{i} = {i}" for i in range(30))
        f = write(self.tmp_path / "m.py", f"def wide():\n{body}\n")
        findings = lint.scan_file(f)
        assert "method-too-long" in rules_for(findings)

    def test_small_method_is_not_flagged(self):
        f = write(self.tmp_path / "m.py", "def narrow():\n    return 1\n")
        assert "method-too-long" not in rules_for(lint.scan_file(f))

    def test_loop_body_over_8_lines_is_flagged(self):
        body = "\n".join(f"        step_{i} = {i}" for i in range(10))
        f = write(self.tmp_path / "loop.py", f"def f(xs):\n    for x in xs:\n{body}\n")
        assert "loop-body-too-long" in rules_for(lint.scan_file(f))

    # ----------------------------------------------------------------------- #
    # Vague names
    # ----------------------------------------------------------------------- #
    def test_vague_file_name_is_flagged(self):
        f = write(self.tmp_path / "utils.py", "x = 1\n")
        assert "vague-file-name" in rules_for(lint.scan_file(f))

    def test_vague_folder_name_is_flagged(self):
        f = write(self.tmp_path / "helpers" / "thing.py", "x = 1\n")
        assert "vague-folder-name" in rules_for(lint.scan_file(f))

    def test_vague_method_name_is_flagged(self):
        f = write(self.tmp_path / "svc.py", "def process():\n    return 1\n")
        assert "vague-method-name" in rules_for(lint.scan_file(f))

    def test_descriptive_name_is_not_flagged(self):
        f = write(self.tmp_path / "stripe_payment_processor.py",
                  "def find_entities():\n    return 1\n")
        assert not (rules_for(lint.scan_file(f)) & {"vague-file-name", "vague-method-name"})

    # ----------------------------------------------------------------------- #
    # Enums
    # ----------------------------------------------------------------------- #
    def test_single_member_enum_is_flagged(self):
        f = write(self.tmp_path / "e.py",
                  "from enum import Enum\n\nclass FooTool(str, Enum):\n    ONLY = 'foo'\n")
        assert "single-member-enum" in rules_for(lint.scan_file(f))

    def test_multi_member_enum_is_allowed(self):
        f = write(self.tmp_path / "e.py",
                  "from enum import Enum\n\nclass Provider(str, Enum):\n"
                  "    LOCAL = 'local'\n    BEDROCK = 'bedrock'\n")
        assert "single-member-enum" not in rules_for(lint.scan_file(f))

    # ----------------------------------------------------------------------- #
    # Module-level state
    # ----------------------------------------------------------------------- #
    def test_module_level_mutable_is_flagged(self):
        f = write(self.tmp_path / "state.py", "cache = {}\n")
        assert "module-level-state" in rules_for(lint.scan_file(f))

    def test_upper_case_constant_is_allowed(self):
        f = write(self.tmp_path / "constants.py", "KNOWN_TF_DIRS = ['terraform', 'infra']\n")
        assert "module-level-state" not in rules_for(lint.scan_file(f))

    # ----------------------------------------------------------------------- #
    # Target discovery
    # ----------------------------------------------------------------------- #
    def test_directory_expands_to_files_and_skips_cache(self):
        write(self.tmp_path / "a.py", "x = 1\n")
        write(self.tmp_path / "__pycache__" / "a.cpython.pyc", "junk\n")
        expanded = lint.expand_paths([self.tmp_path])
        names = {p.name for p in expanded}
        assert "a.py" in names
        assert "a.cpython.pyc" not in names

    def test_non_python_file_gets_only_line_and_name_rules(self):
        f = write(self.tmp_path / "utils.sh", "\n".join(str(i) for i in range(300)))
        rules = rules_for(lint.scan_file(f))
        assert "file-too-long" in rules
        assert "vague-file-name" in rules
        # AST-only rules never fire on a shell script.
        assert not (rules & {"method-too-long", "single-member-enum"})


if __name__ == "__main__":
    unittest.main(verbosity=2)
