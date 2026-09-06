"""The layering rule, enforced rather than described.

    api -> services -> domain -> models

If a route handler could reach past a service into the ORM, someone would
eventually query a category table directly and the permission engine would stop
being the only door -- which is exactly the failure this backend was written to
fix on the client side.
"""
from __future__ import annotations

import ast
import pathlib

ROOT = pathlib.Path(__file__).resolve().parent.parent
ROUTES = sorted((ROOT / "app" / "api").glob("routes_*.py"))
SERVICES = sorted((ROOT / "app" / "services").glob("*.py"))
DOMAIN = sorted((ROOT / "app" / "domain").glob("*.py"))
FRONTEND = ROOT.parent / "ElderApp" / "js"

CATEGORY_TABLES = {
    "Medication", "MedAdministration", "Appointment", "CareNote",
    "FinanceItem", "HandoffNote", "Permission",
}


def imported_modules(path):
    found = set()
    for node in ast.walk(ast.parse(path.read_text())):
        if isinstance(node, ast.Import):
            found.update(alias.name for alias in node.names)
        elif isinstance(node, ast.ImportFrom) and node.module:
            found.add(node.module)
    return found


def imported_names(path):
    found = set()
    for node in ast.walk(ast.parse(path.read_text())):
        if isinstance(node, ast.ImportFrom):
            found.update(alias.name for alias in node.names)
    return found


def identifiers(path):
    """Names used as code, so a word in a docstring is not a finding."""
    found = set()
    for node in ast.walk(ast.parse(path.read_text())):
        if isinstance(node, ast.Name):
            found.add(node.id)
        elif isinstance(node, ast.Attribute):
            found.add(node.attr)
        elif isinstance(node, ast.alias):
            found.add(node.asname or node.name)
    return found


def test_there_are_route_modules_to_check():
    assert len(ROUTES) >= 4


def test_no_route_handler_imports_the_orm():
    for path in ROUTES:
        modules = imported_modules(path)
        assert "app.models" not in modules, "{} reaches into the ORM".format(path.name)
        assert not any(m.startswith("sqlalchemy") for m in modules), path.name


def test_no_route_handler_names_a_category_table():
    for path in ROUTES:
        used = identifiers(path) & CATEGORY_TABLES
        assert not used, "{} names {}".format(path.name, ", ".join(sorted(used)))


def test_no_route_handler_writes_a_query():
    for path in ROUTES:
        source = path.read_text()
        assert "db.query(" not in source
        assert "select(" not in source
        assert "db.get(" not in source


def test_the_domain_layer_has_no_database_dependency():
    """The permission engine must be testable without a database, or it will
    not be tested exhaustively."""
    for path in DOMAIN:
        modules = imported_modules(path)
        assert not any(m.startswith("sqlalchemy") for m in modules), path.name
        assert "app.models" not in modules, path.name
        assert "app.db" not in modules, path.name


def test_every_service_that_reads_a_category_table_goes_through_the_engine():
    engine_names = {"visible_categories", "has_permission", "is_relevant", "withheld_as_irrelevant"}
    exempt = {"activity.py", "people.py", "consent.py", "coverage.py", "delegation.py", "__init__.py"}
    for path in SERVICES:
        if path.name in exempt:
            continue
        source = path.read_text()
        if any(t in source for t in ("Medication", "CareNote", "Appointment", "FinanceItem")):
            assert imported_names(path) & engine_names, (
                "{} reads category data without consulting the permission engine".format(path.name)
            )


def test_the_permission_engine_is_the_only_place_visibility_is_decided():
    engine = ROOT / "app" / "domain" / "permissions.py"
    for path in ROOT.rglob("app/**/*.py"):
        if path == engine:
            continue
        source = path.read_text()
        assert "def has_permission" not in source, path.name
        assert "def is_relevant" not in source, path.name
        assert "def visible_categories" not in source, path.name


def test_there_is_exactly_one_fixed_list_of_categories():
    from app.domain.categories import CATEGORY_ORDER, DataCategory

    assert len(CATEGORY_ORDER) == len(DataCategory) == 6
    assert len(set(CATEGORY_ORDER)) == 6


# --- and the rule that started all of this --------------------------------

def test_the_front_end_no_longer_holds_the_record():
    """The bug this backend fixes.

    `js/data.js` used to keep the permission grid and the activity log in
    localStorage, which meant the whole record reached the browser and the
    browser decided what to draw. Nothing in the client may hardcode a
    permission set again.
    """
    if not FRONTEND.is_dir():  # pragma: no cover - server-only checkout
        return
    for path in FRONTEND.glob("*.js"):
        source = path.read_text()
        assert "presets = {" not in source, "{} hardcodes the presets".format(path.name)
        assert "close_family:" not in source, "{} hardcodes a permission set".format(path.name)
        assert "state.permissions" not in source, "{} keeps a client-side grid".format(path.name)


def test_the_client_never_decides_visibility_from_a_category_list():
    """A section is drawn because the server sent it, never because the client
    checked a list of categories it was also given."""
    if not FRONTEND.is_dir():  # pragma: no cover - server-only checkout
        return
    views = (FRONTEND / "views.js").read_text()
    for pattern in [".includes('mood_notes')", '.includes("mood_notes")',
                    ".includes('finances')", '.includes("finances")']:
        assert pattern not in views, "views.js filters on {} itself".format(pattern)


def test_only_the_ui_slice_is_persisted_in_the_browser():
    if not FRONTEND.is_dir():  # pragma: no cover - server-only checkout
        return
    data = (FRONTEND / "data.js").read_text()
    assert "localStorage" in data, "data.js is still the only file touching storage"
    for leaked in ["permissions", "logs", "handoff", "medsGiven", "buffer"]:
        assert "{}:".format(leaked) not in data, "data.js still persists {}".format(leaked)
