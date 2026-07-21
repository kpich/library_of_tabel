"""Makes ``tests`` a package.

Not decoration: ``test_auth`` imports the credentials from ``tests.conftest``,
and without this file mypy resolves that same file under two module names
(``conftest`` and ``tests.conftest``) and refuses to check anything.
"""
