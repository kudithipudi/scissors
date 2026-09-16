"""Gunicorn configuration for the Rock Paper Scissors FastAPI app."""
import os  # noqa: E402

# Server socket. Defaults to a TCP port so this works out of the box;
# override with e.g. GUNICORN_BIND=unix:/path/to/scissors.sock if you're
# fronting it with nginx/another reverse proxy over a unix socket. Gunicorn
# reads its own config before the app loads `.env`, so set this in the
# actual process environment (systemd `Environment=`, a shell export, etc.),
# not just in `.env`.
bind = os.environ.get('GUNICORN_BIND', '127.0.0.1:8000')
backlog = 2048

# Worker processes (kept at 1: APScheduler runs in-process, and a second
# worker would double-run the cleanup job; fine for this app's traffic).
workers = 1
worker_class = 'uvicorn.workers.UvicornWorker'
timeout = 120
keepalive = 5

# Restart workers after this many requests (helps prevent memory leaks)
max_requests = 1000
max_requests_jitter = 50

# Trust the local nginx proxy's X-Forwarded-* headers (for https scheme in
# generated URLs, e.g. the QR-code join link).
forwarded_allow_ips = '*'

# Logging: local files under app/logs/ (access.log = per-request lines,
# app.log = error/boot log + everything the app emits via `logging`).
# Paths resolve relative to the process's working directory (the systemd
# `WorkingDirectory=`, or wherever you launch gunicorn from).
accesslog = 'app/logs/access.log'
errorlog = 'app/logs/app.log'
# The app logs via logging.basicConfig -> stderr; without this, those lines
# (incl. the per-call "LLM ..." timing) land in journald instead of app.log.
capture_output = True
loglevel = os.environ.get('LOG_LEVEL', 'info')
access_log_format = '%(t)s %(h)s "%(r)s" %(s)s %(b)s %(L)ss'

# Process naming
proc_name = 'scissors'

# Server mechanics
daemon = False
umask = 0
