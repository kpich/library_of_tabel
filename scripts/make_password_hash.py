"""Print a PASSWORD_HASH line for instance/config.py.

    make hash

Prompts twice (never echoing), hashes with Werkzeug, and prints the line to
paste. The password itself is never written anywhere -- only the hash.
"""

from __future__ import annotations

import getpass
import sys

from werkzeug.security import generate_password_hash


def main() -> int:
    password = getpass.getpass("Password: ")
    if not password:
        print("Empty password; nothing to do.", file=sys.stderr)
        return 1
    if password != getpass.getpass("Again: "):
        print("Passwords did not match.", file=sys.stderr)
        return 1

    print("\nPaste this into instance/config.py:\n")
    print(f'PASSWORD_HASH = "{generate_password_hash(password)}"')
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
