"""`domain` must not know that a database or a web framework exists.

Spec invariant 3: a balance is always recomputable from the ledger, and a cache
is never the source of truth. The moment the domain can see an ORM, somebody
will compute a balance by reading a stored column, and the invariant dies
quietly.

Enforced by parsing imports rather than by asking people to remember.
"""

from __future__ import annotations

import ast
import pathlib
import unittest

APP = pathlib.Path(__file__).resolve().parents[1] / "app"
FORBIDDEN_FOR_DOMAIN = ("app.db", "app.api", "app.payments", "sqlalchemy", "fastapi", "alembic", "pydantic")


def imported_modules(path: pathlib.Path) -> set[str]:
    names: set[str] = set()
    for node in ast.walk(ast.parse(path.read_text(encoding="utf-8"))):
        if isinstance(node, ast.Import):
            names.update(alias.name for alias in node.names)
        elif isinstance(node, ast.ImportFrom) and node.module and node.level == 0:
            names.add(node.module)
    return names


class DomainIsPure(unittest.TestCase):
    def test_domain_files_exist(self):
        self.assertTrue(sorted((APP / "domain").glob("*.py")))

    def test_domain_imports_nothing_from_the_outer_layers(self):
        for path in sorted((APP / "domain").glob("*.py")):
            with self.subTest(module=path.name):
                for imported in imported_modules(path):
                    for forbidden in FORBIDDEN_FOR_DOMAIN:
                        self.assertFalse(
                            imported == forbidden or imported.startswith(forbidden + "."),
                            f"{path.name} imports {imported}",
                        )

    def test_payments_is_also_free_of_the_database(self):
        """VietQR only renders a string. It has no business reading tables."""
        payments = APP / "payments"
        if not payments.exists():
            self.skipTest("payments layer not present")
        for path in sorted(payments.glob("*.py")):
            with self.subTest(module=path.name):
                for imported in imported_modules(path):
                    self.assertFalse(imported.startswith("app.db"), f"{path.name} imports {imported}")


if __name__ == "__main__":
    unittest.main()
