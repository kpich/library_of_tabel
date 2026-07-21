"""Makes ``tests`` a package.

Not decoration: ``tests.integration.auth_test`` imports the credentials from
``tests.integration.conftest``, and without an ``__init__.py`` on the way down
mypy resolves that same file under two module names (``conftest`` and
``tests.integration.conftest``) and refuses to check anything.
"""
