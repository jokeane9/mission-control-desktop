#!/usr/bin/env python3
"""P3.1 GitHub auth tests — token validation parsing + connect/status/disconnect
flow with a fake keychain. No network, no real keyring. Stdlib only.
Run: python tests/test_github_auth.py"""
import os, sys, io, json, tempfile, urllib.request

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
import generate
import github_auth as GA


def test_validate_token_parsing():
    orig = urllib.request.urlopen

    class Ctx:
        def __init__(self, payload, exc=None):
            self.payload, self.exc = payload, exc
        def __enter__(self):
            if self.exc:
                raise self.exc
            return io.BytesIO(json.dumps(self.payload).encode())
        def __exit__(self, *a):
            return False

    try:
        urllib.request.urlopen = lambda req, timeout=10: Ctx({"login": "octocat"})
        assert GA.validate_token("x") == "octocat"
        # header carries the token as a Bearer credential
        captured = {}
        def cap(req, timeout=10):
            captured["auth"] = req.headers.get("Authorization")
            return Ctx({"login": "me"})
        urllib.request.urlopen = cap
        GA.validate_token("tok123")
        assert captured["auth"] == "Bearer tok123", captured
        # network/HTTP error → None, never raises
        urllib.request.urlopen = lambda req, timeout=10: Ctx(None, exc=OSError("boom"))
        assert GA.validate_token("x") is None
    finally:
        urllib.request.urlopen = orig


def test_connect_status_disconnect():
    generate.DATA = tempfile.mkdtemp()          # state file lands in a temp dir
    store = {}

    class FakeKR:
        def set_password(self, s, a, v):
            store[(s, a)] = v
        def get_password(self, s, a):
            return store.get((s, a))
        def delete_password(self, s, a):
            store.pop((s, a), None)

    orig_kr, orig_validate = GA._keyring, GA.validate_token
    GA._keyring = lambda: FakeKR()
    GA.validate_token = lambda t, timeout=10: "octocat" if t == "good" else None
    try:
        assert GA.status() == {"connected": False, "login": None}
        assert GA.connect("")["ok"] is False                 # empty
        assert GA.connect("bad")["ok"] is False              # rejected
        assert not store                                     # nothing stored on failure

        r = GA.connect("  good  ")                           # trims + validates + stores
        assert r["ok"] and r["login"] == "octocat"
        assert store                                         # token in (fake) keychain
        assert GA.status() == {"connected": True, "login": "octocat"}
        # token is NOT written to the state file (only the login is)
        state = json.load(open(GA._state_path()))
        assert state == {"login": "octocat"} and "good" not in json.dumps(state)

        GA.disconnect()
        assert GA.status()["connected"] is False
        assert not store and not os.path.exists(GA._state_path())
    finally:
        GA._keyring, GA.validate_token = orig_kr, orig_validate


if __name__ == "__main__":
    tests = [v for k, v in sorted(globals().items()) if k.startswith("test_")]
    for t in tests:
        t()
        print(f"ok  {t.__name__}")
    print(f"\nALL {len(tests)} GITHUB AUTH TESTS PASS")
