"""The migration and the models must not drift apart.

A hand-written migration is the classic place for a schema to fork: the models
grow a table, the migration does not, and the divergence only shows up the
first time somebody runs against a real database.

Two layers:

  * a static comparison of tables and columns parsed from the migration source
  * an actual offline DDL render, which is what catches a migration that
    cannot compile at all

The second layer exists because the first one passed while the migration was
fundamentally broken: five foreign-key names ran past PostgreSQL's 63-character
identifier limit, so the very first deploy would have failed. Alembic renders
DDL with no database attached, so there was never a reason not to check.
Caught in review by Codex.
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
            if not isinstance(func, ast.Attribute):
                continue
            if not node.args or not isinstance(node.args[0], ast.Constant):
                continue
            table = node.args[0].value
            if func.attr == "create_table":
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
                declared.setdefault(table, set()).update(columns)
            elif (
                func.attr == "add_column"
                and len(node.args) >= 2
                and isinstance(node.args[1], ast.Call)
                and isinstance(node.args[1].func, ast.Attribute)
                and node.args[1].func.attr == "Column"
                and node.args[1].args
                and isinstance(node.args[1].args[0], ast.Constant)
            ):
                declared.setdefault(table, set()).add(node.args[1].args[0].value)
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

    def test_the_migration_actually_renders_to_ddl(self):
        """Offline render, no database needed.

        A static name comparison cannot see an identifier PostgreSQL will
        reject, a type that does not exist, or a constraint referencing a table
        declared later. Rendering can.
        """
        import contextlib
        import io
        import os

        from alembic import command
        from alembic.config import Config

        api_root = pathlib.Path(__file__).resolve().parents[2]
        previous = os.getcwd()
        os.chdir(api_root)
        try:
            config = Config(str(api_root / "alembic.ini"))
            config.set_main_option("sqlalchemy.url", "postgresql+psycopg://offline/offline")
            buffer = io.StringIO()
            with contextlib.redirect_stdout(buffer):
                command.upgrade(config, "head", sql=True)
        finally:
            os.chdir(previous)
        self.assertGreaterEqual(buffer.getvalue().count("CREATE TABLE"), len(self.modelled))

    def test_no_identifier_exceeds_the_postgres_limit(self):
        """PostgreSQL truncates identifiers at 63 characters, and a truncated
        name can silently collide with another one."""
        import re
        source = "\n".join(path.read_text(encoding="utf-8") for path in sorted(MIGRATIONS.glob("*.py")))
        source = re.sub(
            r'name=\(\s*((?:"[^"]*"\s*)+)\)',
            lambda m: 'name="' + "".join(re.findall(r'"([^"]*)"', m.group(1))) + '"',
            source,
        )
        names = re.findall(r'name="([a-z0-9_]+)"', source)
        self.assertGreater(len(names), 20, "expected the migration to name its constraints")
        self.assertEqual(sorted({n for n in names if len(n) > 63}), [])
        self.assertEqual(sorted({n for n in names if names.count(n) > 1}), [])

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
