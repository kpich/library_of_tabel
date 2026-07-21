"""Makes ``tests.integration`` a package.

Not decoration: ``auth_test`` imports the credentials from ``conftest``, and
without this file mypy resolves that same file under two module names and
refuses to check anything. See ``tests/__init__.py``.
"""
