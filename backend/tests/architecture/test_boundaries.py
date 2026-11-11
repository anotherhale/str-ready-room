"""Architecture boundary tests.

These prevent the hexagonal dependency direction from eroding:
- the domain must not import FastAPI, SQLAlchemy, or Pydantic transport schemas;
- application services must not import adapters or ORM models;
- SQLAlchemy must be confined to the persistence adapter;
- API routers must not import repositories or SQLAlchemy directly.
"""
from __future__ import annotations

import ast
import pathlib

APP = pathlib.Path(__file__).resolve().parents[2] / "app"

_FORBIDDEN_DOMAIN = {"fastapi", "sqlalchemy", "pydantic", "starlette"}
_FORBIDDEN_APPLICATION = {"fastapi", "sqlalchemy", "starlette"}
_FORBIDDEN_API = {"sqlalchemy"}


def _iter_modules(*parts: str):
    root = APP.joinpath(*parts)
    return sorted(root.rglob("*.py"))


def _imported_modules(path: pathlib.Path) -> set[str]:
    tree = ast.parse(path.read_text(), filename=str(path))
    modules: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                modules.add(alias.name.split(".")[0])
                modules.add(alias.name)
        elif isinstance(node, ast.ImportFrom):
            if node.level and node.level > 0:
                # Relative import; record the tail for adapter checks.
                modules.add("." * node.level + (node.module or ""))
            elif node.module:
                modules.add(node.module.split(".")[0])
                modules.add(node.module)
    return modules


def test_domain_does_not_import_infrastructure():
    offenders = []
    for path in _iter_modules("domain"):
        imported = _imported_modules(path)
        for bad in _FORBIDDEN_DOMAIN:
            if bad in imported:
                offenders.append(f"{path.relative_to(APP)} imports {bad}")
    assert not offenders, offenders


def test_application_does_not_import_adapters_or_orm():
    offenders = []
    for path in _iter_modules("application"):
        imported = _imported_modules(path)
        for bad in _FORBIDDEN_APPLICATION:
            if bad in imported:
                offenders.append(f"{path.relative_to(APP)} imports {bad}")
        # Relative imports must not reach into adapters.
        for name in imported:
            if name.startswith("..") and "adapters" in name:
                offenders.append(f"{path.relative_to(APP)} imports adapters via {name}")
    assert not offenders, offenders


def test_sqlalchemy_confined_to_persistence_adapter():
    offenders = []
    for path in APP.rglob("*.py"):
        rel = path.relative_to(APP)
        if rel.parts[:3] == ("adapters", "persistence", "sqlalchemy"):
            continue
        imported = _imported_modules(path)
        if "sqlalchemy" in imported:
            offenders.append(str(rel))
    assert not offenders, offenders


def test_api_does_not_import_sqlalchemy_or_repositories():
    offenders = []
    for path in _iter_modules("api"):
        imported = _imported_modules(path)
        for bad in _FORBIDDEN_API:
            if bad in imported:
                offenders.append(f"{path.relative_to(APP)} imports {bad}")
        if "repositories" in imported:
            offenders.append(f"{path.relative_to(APP)} imports repositories")
    assert not offenders, offenders


def test_domain_is_pure_of_pydantic_transport_schemas():
    offenders = []
    for path in _iter_modules("domain"):
        source = path.read_text()
        if "schemas.requests" in source or "schemas.responses" in source:
            offenders.append(str(path.relative_to(APP)))
    assert not offenders, offenders
