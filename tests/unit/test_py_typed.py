"""Tests that the package ships a PEP 561 ``py.typed`` marker."""

import pathlib

import py_moodle


def test_py_typed_marker_is_present():
    """The ``py_moodle`` package should include a ``py.typed`` marker.

    Per PEP 561, the presence of ``py.typed`` inside the installed package
    tells type checkers (mypy/pyright) that the package ships inline type
    annotations and should be treated as typed by downstream consumers.
    """
    package_dir = pathlib.Path(py_moodle.__file__).parent
    marker = package_dir / "py.typed"

    assert marker.is_file()
