"""
WSGI entry-point for production servers (Gunicorn, uWSGI, etc.).

Usage:
    gunicorn wsgi:application --bind 0.0.0.0:$PORT
"""
from app import create_app

application = create_app()
