"""Shared helpers for the Chat B hooks."""
import os
import re
from urllib.parse import urlparse

HOOKS_DIR = os.path.dirname(os.path.abspath(__file__))
LOG_DIR = os.path.join(os.path.dirname(HOOKS_DIR), "logs")


def allowed_sites():
    path = os.path.join(HOOKS_DIR, "allowed_sites.txt")
    with open(path, encoding="utf-8") as f:
        return [
            line.strip().lower()
            for line in f
            if line.strip() and not line.strip().startswith("#")
        ]


def host_of(url):
    url = (url or "").strip()
    if not re.match(r"^[a-zA-Z][a-zA-Z0-9+.-]*://", url):
        url = "https://" + url
    return (urlparse(url).hostname or "").lower()


def is_allowed(url):
    host = host_of(url)
    if not host:
        return False
    return any(host == site or host.endswith("." + site) for site in allowed_sites())


def normalize(url):
    """Make two links to the same page compare equal."""
    url = (url or "").strip().strip('"').strip("'")
    if not re.match(r"^[a-zA-Z][a-zA-Z0-9+.-]*://", url):
        url = "https://" + url
    p = urlparse(url)
    host = (p.hostname or "").lower()
    if host.startswith("www."):
        host = host[4:]
    path = p.path.rstrip("/")
    query = ("?" + p.query) if p.query else ""
    return host + path + query


def sources_log(session_id):
    os.makedirs(LOG_DIR, exist_ok=True)
    safe = re.sub(r"[^A-Za-z0-9_-]", "_", session_id or "unknown")
    return os.path.join(LOG_DIR, f"sources-{safe}.txt")
