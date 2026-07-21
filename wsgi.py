"""WSGI entry point.

PythonAnywhere's web tab imports this module and looks for a module-level
callable named ``application`` -- the name matters, don't rename it.
"""

from app import create_app

application = create_app()
