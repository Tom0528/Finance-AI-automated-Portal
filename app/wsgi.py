"""
WSGI entry-point for production servers and Vercel.

- Gunicorn (Render / Railway):  gunicorn wsgi:application
- Vercel Python runtime:        looks for a variable named 'app'
"""
from app import create_app

application = create_app()
app = application          # Vercel requires the variable to be named 'app'
