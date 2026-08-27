"""The migration and the models must not drift apart.

A hand-written migration is the classic place for a schema to fork: the models
grow a table, the migration does not, and the divergence only shows up the
first time somebody runs against a real database.

This is a STATIC comparison. It parses the migration source and checks that the
same tables and columns appear on both sides. It does NOT prove the migration
executes -- that needs a live PostgreSQL and is not attempted here.
"""

from __future__ import annotations

import ast
import pathlib
import sys
import unittest

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[2]))

from app.db import models  # noqa: F401,E402  (import registers the tables)
from app.db.base import Base  # noqa: E402

MIGRATIONS = pathlib.Path(__file__).resolve().parents[2] / "app/db/migrations/versions"


def tables_declared_in_migrations() -> dict[str, set[str]]:
    declared: dict[str, set[str]] = {}
    for path in sorted(MIGRATIONS.glob("*.py")):
        tree = ast.parse(path.read_text(encoding="utf-8"))
        for node in ast.walk(tree):
            if not isinstance(node, ast.Call):
                continue
            func = node.func
            if not (isinstance(func, ast.Attribute) and func.attr == "create_table"):
                continue
            if not node.args or not isinstance(node.args[0], ast.Constant):
                continue
            table = node.args[0].value
            columns = set()
            for argument in node.args[1:]:
                if (
                    isinstance(argument, ast.Call)
                    and isinstance(argument.func, ast.Attribute)
                    and argument.func.attr == "Column"
                    and argument.args
                    and isinstance(argument.args[0], ast.Constant)
                ):
                    columns.add(argument.args[0].value)
            declared[table] = columns
    return declared


class MigrationMatchesModels(unittest.TestCase):
    def setUp(self):
        self.declared = tables_declared_in_migrations()
        self.modelled = {
            name: {column.name for column in table.columns}
            for name, table in Base.metadata.tables.items()
        }

    def test_same_set_of_tables(self):
        self.assertEqual(sorted(self.declared), sorted(self.modelled))

    def test_same_columns_per_table(self):
        for table in sorted(self.modelled):
            with self.subTest(table=table):
                self.assertEqual(
                    sorted(self.declared.get(table, set())),
                    sorted(self.modelled[table]),
                )

    def test_no_money_column_uses_a_lossy_type(self):
        """Spec section 4, invariant 2: integer dong, never a float.

        Numeric would technically be exact, but it invites Decimal into the
        domain and from there a float is one careless division away.
        """
        for name, table in Base.metadata.tables.items():
            for column in table.columns:
                if column.name.endswith("_vnd"):
                    with self.subTest(table=name, column=column.name):
                        self.assertEqual(type(column.type).__name__, "BigInteger")


if __name__ == "__main__":
    unittest.main()
