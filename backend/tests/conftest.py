import os

# Must run before app modules are imported (settings are cached at import time).
os.environ.setdefault("RATE_LIMIT_NEW_ANALYSES", "1000/minute")
os.environ["APP_ROLE"] = "all"  # the image defaults to api
