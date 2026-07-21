"""Example configuration -- copy to instance/config.py and fill in.

    mkdir -p instance
    cp config.example.py instance/config.py
    make hash          # prints a PASSWORD_HASH line to paste below

instance/ is gitignored. Nothing in this file's real counterpart may ever be
committed. Every key here can equivalently be set as a TL_<KEY> environment
variable, which takes precedence over this file.
"""

# Flask session signing key. Any long random string; keep it stable or every
# login session is invalidated. Generate one with:
#     python -c "import secrets; print(secrets.token_hex(32))"
SECRET_KEY = "replace-me"

# Werkzeug password hash -- NOT the password itself. Produce it with `make hash`.
PASSWORD_HASH = "replace-me"

# The single user's login name. There is exactly one user; there is no signup.
USERNAME = "me"

# Send cookies only over HTTPS. Off by default: a secure cookie over plain http
# is silently dropped by the browser, and local development is plain http --
# the failure looks like "logging in does nothing". Turn it on wherever the app
# is served over HTTPS (PythonAnywhere is, so deploy sets
# TL_SESSION_COOKIE_SECURE=1 there). REMEMBER_COOKIE_SECURE follows this unless
# set explicitly.
# SESSION_COOKIE_SECURE = True

# Where the library lives. This is the separate PRIVATE data repo, normally
# cloned alongside this one, and it defaults to ../library_of_tabel_data.
# Point it at "samples" to run against the sample entries in this repo.
# DATA_DIR = "/absolute/path/to/library_of_tabel_data"
