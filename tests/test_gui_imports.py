"""Smoke tests for the Tkinter GUI module.

The GUI itself needs a display to fully instantiate, but we can still
catch a common class of bugs (tuple padx/pady passed to widget
constructors, which Tk rejects with 'bad screen distance') via static
AST inspection of the module source.
"""

import ast
import importlib
import pathlib


def test_gui_module_imports():
    """Importing the module must not raise (no display required)."""
    importlib.import_module("dolphin2mintpy.gui")


def test_no_tuple_padx_pady_in_widget_constructors():
    """Constructor calls must not pass tuples to padx / pady.

    tk.Widget(padx=..., pady=...) only accepts a single screen distance.
    Tuples are valid on pack()/grid() but raise at run-time when passed
    to a widget constructor, producing errors such as
    ``bad screen distance '8 2'``.
    """
    source = (
        pathlib.Path(__file__).resolve().parent.parent
        / "src" / "dolphin2mintpy" / "gui.py"
    ).read_text(encoding="utf-8")
    tree = ast.parse(source)

    offenders: list[str] = []
    for node in ast.walk(tree):
        if not isinstance(node, ast.Call):
            continue
        func = node.func
        # Widget constructors look like tk.Label(...), ttk.Frame(...),
        # scrolledtext.ScrolledText(...) - ast.Attribute nodes.
        if not isinstance(func, ast.Attribute):
            continue
        # pack() / grid() / configure() are methods on an existing
        # widget; skip them.
        if func.attr in {"pack", "grid", "configure", "place", "after"}:
            continue
        for kw in node.keywords:
            if kw.arg in {"padx", "pady"} and isinstance(kw.value, ast.Tuple):
                offenders.append(
                    f"{func.attr}(...) at line {node.lineno}: "
                    f"{kw.arg}=(...) tuple"
                )

    assert not offenders, (
        "Widget constructors received tuple padx/pady. Move tuple "
        "paddings onto .pack()/.grid() instead:\n  "
        + "\n  ".join(offenders)
    )
