"""Application settings. Conventions:

- Every timestamp in the database is naive UTC; compare it only with `datetime.utcnow()`.
- The app runs behind the company load balancer. `request.remote_addr` is already the real
  client address: the balancer strips client-supplied forwarding headers at the WSGI layer and
  sets REMOTE_ADDR itself. Headers such as `X-Forwarded-For` reach the app exactly as the
  client sent them.
- Four worker processes serve requests on each host.
"""
import os


class Settings:
    BASE_URL = os.environ.get("BASE_URL", "https://app.example.com")
    DATABASE_URL = os.environ["DATABASE_URL"]
    LOG_LEVEL = os.environ.get("LOG_LEVEL", "INFO")


settings = Settings()
