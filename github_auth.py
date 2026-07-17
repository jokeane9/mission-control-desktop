#!/usr/bin/env python3
"""GitHub auth for Orrery (P3.1). The token lives in the OS keychain and
nowhere else; there is no repo sync yet (that's github_sync.py, P3.2). The only
network call is validating a token the user pasted, against GitHub's /user.

Kept out of generate.py/resolve.py on purpose: those stay offline + stdlib. This
module is imported by app.py (the side that already has dependencies)."""
import json, os, urllib.request

import generate  # for the per-user data dir (generate.DATA)

_SERVICE = "Orrery-GitHub"
_LEGACY_SERVICE = "MissionControl-GitHub"   # pre-2.0; see get_token()
_ACCOUNT = "pat"


def _state_path():
    return os.path.join(generate.DATA, "github.json")


# --- token: OS keychain only ------------------------------------------------
def _keyring():
    import keyring  # lazy: an absent/broken keyring degrades to "disconnected"
    return keyring


def store_token(token):
    _keyring().set_password(_SERVICE, _ACCOUNT, token)


def get_token():
    """The stored PAT, or None. v2.0.0 renamed the keychain service along with
    the app; a token saved before that still lives under the old name. Fall back
    to it and re-save under the new one, so the rename doesn't silently log the
    user out (an absent token degrades to "disconnected" — it would look like a
    bug, not a migration). Removal criterion: drop the fallback once no
    supported version predates 2.0.0."""
    try:
        token = _keyring().get_password(_SERVICE, _ACCOUNT)
    except Exception:
        return None
    if token:
        return token
    try:
        token = _keyring().get_password(_LEGACY_SERVICE, _ACCOUNT)
        if token:
            _keyring().set_password(_SERVICE, _ACCOUNT, token)
        return token
    except Exception:
        return None


def clear_token():
    """Disconnect. Clears both names — leaving the legacy entry behind would let
    get_token() resurrect it on the next call."""
    for svc in (_SERVICE, _LEGACY_SERVICE):
        try:
            _keyring().delete_password(svc, _ACCOUNT)
        except Exception:
            pass


# --- non-secret cached login, so status() needs no network ------------------
def _read_state():
    try:
        return json.load(open(_state_path(), encoding="utf-8"))
    except Exception:
        return {}


def _write_state(d):
    try:
        with open(_state_path(), "w", encoding="utf-8") as f:
            json.dump(d, f)
    except Exception:
        pass


def _clear_state():
    try:
        os.remove(_state_path())
    except Exception:
        pass


# --- GitHub API -------------------------------------------------------------
def validate_token(token, timeout=10):
    """GET /user with the token. Returns the login (str) if valid, else None."""
    req = urllib.request.Request(
        "https://api.github.com/user",
        headers={"Authorization": f"Bearer {token}",
                 "Accept": "application/vnd.github+json",
                 "User-Agent": "Mission-Control"})
    try:
        with urllib.request.urlopen(req, timeout=timeout) as r:
            return json.load(r).get("login")
    except Exception:
        return None


# --- the three operations the bridge exposes --------------------------------
def connect(token):
    """Validate then store. Returns {ok, login} or {ok: False, error}."""
    token = (token or "").strip()
    if not token:
        return {"ok": False, "error": "No token provided."}
    login = validate_token(token)
    if not login:
        return {"ok": False, "error": "GitHub rejected that token."}
    store_token(token)
    _write_state({"login": login})
    return {"ok": True, "login": login}


def status():
    """Offline: token present + the login cached at connect time. No network."""
    if not get_token():
        return {"connected": False, "login": None}
    return {"connected": True, "login": _read_state().get("login")}


def disconnect():
    clear_token()
    _clear_state()
    return {"ok": True}
