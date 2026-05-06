"""
test_import_smoke.py — Verify the run.py importlib shim loads correctly.

This is the Phase 1 gate test. If this passes, all CLI tests are unblocked.
If this fails, the import strategy in run.py needs to be fixed before
any other CLI tests can be written.

Author: Scott Adams (msadams) — 2026-03-09
"""

from pathlib import Path


def test_deft_module_loads(deft_module) -> None:
    """The run.py shim must load the deft CLI without errors."""
    assert deft_module is not None


def test_get_script_dir_returns_path(deft_module) -> None:
    """get_script_dir() must return a valid Path pointing to the repo root."""
    result = deft_module.get_script_dir()
    assert isinstance(result, Path)
    assert result.is_dir()


def test_get_default_paths_has_expected_keys(deft_module) -> None:
    """get_default_paths() must return a dict with all expected path keys."""
    paths = deft_module.get_default_paths()
    assert isinstance(paths, dict)
    assert "user" in paths
    assert "project" in paths
    assert "prd" in paths
    assert "specification" in paths


def test_version_is_string(deft_module) -> None:
    """VERSION must be a non-empty string."""
    assert isinstance(deft_module.VERSION, str)
    assert len(deft_module.VERSION) > 0


def test_cmd_functions_are_callable(deft_module) -> None:
    """Core cmd_* functions must be importable and callable."""
    assert callable(deft_module.cmd_bootstrap)
    assert callable(deft_module.cmd_project)
    assert callable(deft_module.cmd_validate)
    assert callable(deft_module.cmd_doctor)
