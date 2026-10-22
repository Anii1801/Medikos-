import os

# The suite makes hundreds of auth calls from one test client; limiter behaviour has its own dedicated tests.
os.environ.setdefault("MEDIKIOSK_RATE_LIMIT", "off")
