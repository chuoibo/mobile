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


def _upgrade_bodies() -> list[tuple[str, ast.FunctionDef]]:
    """Every `upgrade()`, in revision order, with its source.

    Two things here were wrong before and both only showed up the first time a
    migration removed something rather than adding it.

    **Only `upgrade()`.** The old reader walked the whole module, so a
    `downgrade()` that correctly re-creates what it dropped looked like a table
    the models were missing. A migration's forward direction is what the
    database ends up in; that is what these cases are about.

    **Revision order, not filename order.** Filenames are hex and sort
    arbitrarily. That never mattered while every migration only added -- a
    union is order-free -- and it matters completely once one of them drops.
    """

    by_revision: dict[str, tuple[str, ast.Module, ast.FunctionDef]] = {}
    parents: dict[str, str | None] = {}
    for path in MIGRATIONS.glob("*.py"):
        source = path.read_text(encoding="utf-8")
        tree = ast.parse(source)
        revision = down = None
        upgrade = None
        for node in tree.body:
            if isinstance(node, ast.FunctionDef) and node.name == "upgrade":
                upgrade = node
            target = None
            if isinstance(node, ast.AnnAssign) and isinstance(node.target, ast.Name):
                target, value = node.target.id, node.value
            elif isinstance(node, ast.Assign) and isinstance(node.targets[0], ast.Name):
                target, value = node.targets[0].id, node.value
            if target == "revision" and isinstance(value, ast.Constant):
                revision = value.value
            elif target == "down_revision" and isinstance(value, ast.Constant):
                down = value.value
        assert revision is not None and upgrade is not None, path.name
        by_revision[revision] = (source, tree, upgrade)
        parents[revision] = down

    children = {down: rev for rev, down in parents.items()}
    ordered: list[tuple[str, ast.FunctionDef]] = []
    current = children.get(None)
    while current is not None:
        source, _tree, upgrade = by_revision[current]
        ordered.append((source, upgrade))
        current = children.get(current)
    assert len(ordered) == len(by_revision), (
        "the revision chain is broken or branched; "
        f"walked {len(ordered)} of {len(by_revision)}"
    )
    return ordered


def tables_declared_in_migrations() -> dict[str, set[str]]:
    declared: dict[str, set[str]] = {}
    for _source, upgrade in _upgrade_bodies():
        for node in ast.walk(upgrade):
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
            elif func.attr == "drop_table":
                declared.pop(table, None)
            elif func.attr == "drop_column" and len(node.args) >= 2:
                # `op.drop_column(table, column)`. Dropping a column from a
                # table that was never declared here is a bug in the migration,
                # not something to swallow, but this reader is not the gate for
                # that -- the offline render below is.
                column = node.args[1]
                if isinstance(column, ast.Constant):
                    declared.get(table, set()).discard(column.value)
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
            config.set_main_option(
                "sqlalchemy.url", "postgresql+psycopg://offline/offline"
            )
            buffer = io.StringIO()
            with contextlib.redirect_stdout(buffer):
                command.upgrade(config, "head", sql=True)
        finally:
            os.chdir(previous)
        self.assertGreaterEqual(
            buffer.getvalue().count("CREATE TABLE"), len(self.modelled)
        )

    def test_no_identifier_exceeds_the_postgres_limit(self):
        """PostgreSQL truncates identifiers at 63 characters, and a truncated
        name can silently collide with another one."""
        import re

        # Forward direction only, for the same reason the reader above changed:
        # a `downgrade()` that re-creates a constraint it just dropped reuses
        # the name on purpose, and counting that as a duplicate turns a correct
        # migration red. What this case is about is two DIFFERENT objects
        # claiming one name as the schema moves forward.
        source = "\n".join(
            ast.get_source_segment(text, upgrade) or ""
            for text, upgrade in _upgrade_bodies()
        )
        source = re.sub(
            r'name=\(\s*((?:"[^"]*"\s*)+)\)',
            lambda m: 'name="' + "".join(re.findall(r'"([^"]*)"', m.group(1))) + '"',
            source,
        )
        # `(?<![a-z_])` so `table_name="memories"` is not harvested as a
        # constraint called `memories`. It was, and the duplicate check below
        # then failed the moment a second migration dropped an index on a
        # table an earlier one had already dropped an index on -- a collision
        # between two table references, not between two identifiers.
        names = re.findall(r'(?<![a-z_])name="([a-z0-9_]+)"', source)
        self.assertGreater(
            len(names), 20, "expected the migration to name its constraints"
        )
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
