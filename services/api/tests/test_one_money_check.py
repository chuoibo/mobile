"""One integer-quantity check, in one file, found by SHAPE rather than by name.

Money law 1 says a sum of đồng is an integer number of đồng -- no float, no
`Decimal`, and specifically not `bool`, because `isinstance(True, int)` is true
in Python and `True` would otherwise become one đồng.

`ledger.require_vnd` was written to be the one place that says so. It did not
stay the one place. Two independent counts found copies of its body pasted
around the tree, and each count was blind in its own way:

  * counting by the error code `AMOUNT_NOT_INTEGER` found four, and missed
    three copies that raise a module-local code instead
    (`INVALID_BUDGET_INPUT`, `place_search_budget_not_integer`,
    `suggestion_history_not_integer_dong`);
  * counting by export name found seven, and missed a copy that grew a new
    money parameter inside a function that already existed.

Both blind spots have the same cause: the copies were counted by something a
copier is free to change. So this gate counts the one thing a copy cannot lose
and still be a copy -- the shape of the predicate itself:

    isinstance(V, bool)  ...  isinstance(V, int)      on the same V

Order, `and`/`or`, `not`, the comparison that follows and the exception raised
are all free to vary; the pair of `isinstance` calls is what makes it this
check. A rewrite in any of those free dimensions still trips this gate, which
is the point -- the previous two gates were defeated by exactly such a rewrite.

A third spelling says the same thing without any `bool` call at all, because
`type(True) is bool` already excludes it:

    type(V) is int  /  type(V) is not int

That one is counted too. It is not a hypothetical: the first draft of this
gate could not see it, and neither could the independent count that corrected
four to six -- and it hid `money_skill._strict_positive_int`, a real đồng
check capped at `MAX_AMOUNT_VND`. Six was still short. The lesson is the same
one that produced this file: every count so far was blind to something a
copier was free to change, so the gate counts every spelling it knows and says
plainly, below, which ones it does not.

What this gate does NOT prove, stated plainly:

  * It does not prove the copies behaved identically before they were merged.
    Two did not: `settlement_plan` validates a *signed* balance (the balances
    must net to zero, so negatives are required) and `vietqr` collapses
    negative and zero into one code. Those are covered by their own tests.
  * It does not cover `app/web/`, which is another lane's code. `web/
    guest_view.py:format_vnd` holds a seventh copy of this shape and is
    reported to the Lead rather than edited here. `SCOPE` below is the honest
    boundary of this measurement, not a claim about the whole tree.
  * A quantity check written some FOURTH way -- a `numbers.Integral` test, a
    `try: int(v)`, a regex over a string -- is a shape this matcher does not
    know. It catches the two spellings that exist in this tree today, not
    every conceivable rewrite. If a count taken some other way disagrees with
    this one, that count is the interesting one, and this file should grow.
"""

from __future__ import annotations

import ast
import pathlib
import unittest

APP = pathlib.Path(__file__).resolve().parents[1] / "app"

# The layers this lane owns. `app/web/` belongs to another lane and is
# deliberately outside the measurement; see the module docstring.
SCOPE = ("domain", "payments", "api", "db")

# The one file allowed to spell the predicate out. Everything else calls it.
HOME = APP / "domain" / "money.py"


def _class_names(classinfo: ast.expr) -> set[str]:
    if isinstance(classinfo, ast.Tuple):
        return {e.id for e in classinfo.elts if isinstance(e, ast.Name)}
    if isinstance(classinfo, ast.Name):
        return {classinfo.id}
    return set()


def _collect(node: ast.AST, scope: str, buckets: dict) -> None:
    """Attribute each `isinstance` call to its NEAREST enclosing function.

    Nearest-enclosing rather than "anywhere underneath": walking the module as
    one scope makes every function's calls also the module's, so an
    `isinstance(x, bool)` in one function and an `isinstance(x, int)` in
    another pair up into a copy that is not there. The matcher self-checks
    below caught exactly that in the first draft of this file.

    The subject is rendered back to source, so `value`, `expense["total_vnd"]`
    and `self.amount` compare as the distinct expressions they are.
    """
    for child in ast.iter_child_nodes(node):
        if isinstance(child, ast.FunctionDef | ast.AsyncFunctionDef):
            _collect(child, child.name, buckets)
            continue
        if (
            isinstance(child, ast.Call)
            and isinstance(child.func, ast.Name)
            and child.func.id == "isinstance"
            and len(child.args) == 2
        ):
            subject, classinfo = child.args
            names = _class_names(classinfo)
            here = buckets.setdefault(
                scope, {"bool": set(), "int": set(), "type_int": set()}
            )
            if "bool" in names:
                here["bool"].add(ast.unparse(subject))
            # `== {"int"}` and not `"int" in names`: a check that also admits
            # `float` is a different check. `place_search._distance_km` rejects
            # `bool` and accepts `(int, float)` on purpose -- a fraction of a
            # kilometre is a real distance, not a lost đồng -- and must not be
            # dragged into a validator named for money.
            if names == {"int"}:
                here["int"].add(ast.unparse(subject))
        elif (
            isinstance(child, ast.Compare)
            and isinstance(child.left, ast.Call)
            and isinstance(child.left.func, ast.Name)
            and child.left.func.id == "type"
            and len(child.left.args) == 1
            and len(child.ops) == 1
            and isinstance(child.ops[0], ast.Is | ast.IsNot)
            and isinstance(child.comparators[0], ast.Name)
            and child.comparators[0].id == "int"
        ):
            # `type(v) is not int` is the same rule in a third spelling. It
            # needs no companion `bool` call -- `type(True) is bool` -- which
            # is exactly why the first draft of this gate could not see it and
            # why qa2's independent count could not either. Both counts missed
            # `money_skill._strict_positive_int`, a real đồng check.
            here = buckets.setdefault(
                scope, {"bool": set(), "int": set(), "type_int": set()}
            )
            here["type_int"].add(ast.unparse(child.left.args[0]))
        _collect(child, scope, buckets)


def inline_quantity_checks(source: str) -> set[str]:
    """Names of the scopes in `source` that spell the predicate out inline."""
    buckets: dict[str, dict[str, set[str]]] = {}
    _collect(ast.parse(source), "<module>", buckets)
    return {
        scope
        for scope, seen in buckets.items()
        if (seen["bool"] & seen["int"]) or seen["type_int"]
    }


def scoped_files() -> list[pathlib.Path]:
    paths: list[pathlib.Path] = []
    for layer in SCOPE:
        paths.extend(sorted((APP / layer).rglob("*.py")))
    return paths


class TheMatcherItselfWorks(unittest.TestCase):
    """Without these, a zero below could mean 'clean' or 'matcher broken'."""

    def test_it_finds_the_shape_it_is_looking_for(self):
        source = (
            "def f(value):\n"
            "    if isinstance(value, bool) or not isinstance(value, int):\n"
            "        raise E('x')\n"
        )
        self.assertEqual(inline_quantity_checks(source), {"f"})

    def test_it_finds_the_shape_written_backwards(self):
        """A copier who reorders the two calls has still copied the check."""
        source = (
            "def f(value):\n"
            "    if not isinstance(value, int) or isinstance(value, bool):\n"
            "        raise E('x')\n"
        )
        self.assertEqual(inline_quantity_checks(source), {"f"})

    def test_it_finds_the_shape_outside_an_if(self):
        """A ternary is where an AST gate in this repo has gone blind before."""
        source = (
            "def f(value):\n"
            "    bad = isinstance(value, bool) or not isinstance(value, int)\n"
            "    return None if bad else value\n"
        )
        self.assertEqual(inline_quantity_checks(source), {"f"})

    def test_it_does_not_fire_on_the_near_miss_already_in_the_tree(self):
        """Verbatim `place_search._distance_km`: rejects bool, allows float.

        The closest thing in the tree to a false positive. It shares the
        `bool` rejection but admits a fraction on purpose, so it is not the
        đồng predicate and must not be pulled into `money.py`.
        """
        source = (
            "def _distance_km(value):\n"
            "    if value is None:\n"
            "        return None\n"
            "    if isinstance(value, bool) or not isinstance(value, (int, float))"
            " or value <= 0:\n"
            "        raise _malformed()\n"
            "    return value\n"
        )
        self.assertEqual(inline_quantity_checks(source), set())

    def test_it_finds_the_third_spelling(self):
        """`type(v) is not int` needs no `bool` call to reject `True`.

        Verbatim `money_skill._strict_positive_int`, which BOTH counts missed
        -- and it is đồng, capped at `MAX_AMOUNT_VND`.
        """
        source = (
            "def _strict_positive_int(value):\n"
            "    return type(value) is int and 0 < value <= MAX_AMOUNT_VND\n"
        )
        self.assertEqual(inline_quantity_checks(source), {"_strict_positive_int"})

    def test_it_finds_the_third_spelling_negated(self):
        source = (
            "def f(value):\n"
            "    if type(value) is not int or value <= 0:\n"
            "        raise E('x')\n"
        )
        self.assertEqual(inline_quantity_checks(source), {"f"})

    def test_it_ignores_the_same_spelling_aimed_at_bool(self):
        """`type(x) is not bool` is a flag check, not a quantity check."""
        source = (
            "def f(in_progress):\n"
            "    if type(in_progress) is not bool:\n"
            "        raise E('x')\n"
        )
        self.assertEqual(inline_quantity_checks(source), set())

    def test_it_does_not_pair_two_unrelated_functions(self):
        source = (
            "def f(value):\n"
            "    return isinstance(value, bool)\n"
            "def g(value):\n"
            "    return isinstance(value, int)\n"
        )
        self.assertEqual(inline_quantity_checks(source), set())


class OneCheckOnly(unittest.TestCase):
    def test_the_scope_is_not_empty(self):
        """A typo in SCOPE would make every assertion below vacuously true."""
        self.assertGreater(len(scoped_files()), 10)

    def test_the_shared_check_still_exists_where_it_belongs(self):
        """Positive control: deleting `money.py` must not read as 'no copies'."""
        self.assertTrue(HOME.exists(), f"{HOME} is gone")
        self.assertTrue(
            inline_quantity_checks(HOME.read_text(encoding="utf-8")),
            f"{HOME.name} no longer contains the check it is supposed to own",
        )

    def test_nobody_else_spells_the_check_out_inline(self):
        for path in scoped_files():
            if path == HOME:
                continue
            with self.subTest(module=str(path.relative_to(APP))):
                self.assertEqual(
                    inline_quantity_checks(path.read_text(encoding="utf-8")),
                    set(),
                    f"{path.relative_to(APP)} re-implements the check that "
                    f"{HOME.name} owns; call it instead",
                )


if __name__ == "__main__":
    unittest.main()
