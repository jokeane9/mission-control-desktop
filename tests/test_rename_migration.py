#!/usr/bin/env python3
"""v2.0.0 rename migrations — the three user-facing surfaces keyed off the old
app name. Each of these fails SILENTLY if it regresses (empty dashboard, a
surprise logout, cards that quietly stop resolving), so they get tests rather
than trust.

  1. data dir      Mission Control/ -> Orrery/   (generate._migrate_data_dir)
  2. keychain      MissionControl-GitHub -> Orrery-GitHub  (github_auth)
  3. block files   .mission-control.* -> .orrery.*         (resolve.read_block)

Stdlib only; run: python tests/test_rename_migration.py"""
import json, os, shutil, sys, tempfile

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
import generate
import github_auth as GA
import resolve as R


# --- 1. data dir ------------------------------------------------------------ #
def test_data_dir_migrates_legacy_config():
    base = tempfile.mkdtemp()
    try:
        old = os.path.join(base, generate.LEGACY_APP_NAME)
        os.makedirs(old)
        open(os.path.join(old, "baseline.json"), "w").write('{"projects":[1]}')
        open(os.path.join(old, "pm_notes.md"), "w").write("my notes")
        new = os.path.join(base, generate.APP_NAME)

        assert generate._migrate_data_dir(base, new) is True
        assert json.load(open(os.path.join(new, "baseline.json")))["projects"] == [1]
        assert open(os.path.join(new, "pm_notes.md")).read() == "my notes"
        # copy, not move: the old dir survives as a fallback if anything went wrong
        assert os.path.isfile(os.path.join(old, "baseline.json"))
    finally:
        shutil.rmtree(base, ignore_errors=True)


def test_data_dir_never_clobbers_existing():
    """The migration must be a one-shot. If the new dir already exists, real
    current config lives there — copying over it would destroy live data."""
    base = tempfile.mkdtemp()
    try:
        old = os.path.join(base, generate.LEGACY_APP_NAME)
        new = os.path.join(base, generate.APP_NAME)
        os.makedirs(old); os.makedirs(new)
        open(os.path.join(old, "baseline.json"), "w").write('{"projects":["OLD"]}')
        open(os.path.join(new, "baseline.json"), "w").write('{"projects":["NEW"]}')

        assert generate._migrate_data_dir(base, new) is False
        assert json.load(open(os.path.join(new, "baseline.json")))["projects"] == ["NEW"]
    finally:
        shutil.rmtree(base, ignore_errors=True)


def test_data_dir_fresh_install_is_a_noop():
    base = tempfile.mkdtemp()
    try:
        new = os.path.join(base, generate.APP_NAME)
        assert generate._migrate_data_dir(base, new) is False   # no legacy dir
    finally:
        shutil.rmtree(base, ignore_errors=True)


def test_data_dir_migration_failure_is_not_fatal():
    """A migration that raises must never stop the app booting — worst case the
    user re-adds projects; a crash-on-launch is unshippable."""
    base = tempfile.mkdtemp()
    try:
        os.makedirs(os.path.join(base, generate.LEGACY_APP_NAME))
        new = os.path.join(base, generate.APP_NAME)
        orig = shutil.copytree
        shutil.copytree = lambda *a, **k: (_ for _ in ()).throw(OSError("boom"))
        try:
            assert generate._migrate_data_dir(base, new) is False   # no raise
            assert os.path.isdir(new)                               # usable anyway
        finally:
            shutil.copytree = orig
    finally:
        shutil.rmtree(base, ignore_errors=True)


# --- 2. keychain ------------------------------------------------------------ #
class FakeKR:
    def __init__(self, store):
        self.store = store
    def set_password(self, s, a, v):
        self.store[(s, a)] = v
    def get_password(self, s, a):
        return self.store.get((s, a))
    def delete_password(self, s, a):
        self.store.pop((s, a), None)


def _with_fake_keyring(store, fn):
    orig = GA._keyring
    GA._keyring = lambda: FakeKR(store)
    try:
        return fn()
    finally:
        GA._keyring = orig


def test_keychain_reads_legacy_token_and_upgrades_it():
    """A token stored pre-2.0 must keep working. It degrades to 'disconnected'
    rather than erroring, so a regression here looks like a bug, not a rename."""
    store = {(GA._LEGACY_SERVICE, GA._ACCOUNT): "ghp_legacy"}
    assert _with_fake_keyring(store, GA.get_token) == "ghp_legacy"
    # re-saved under the new name, so the fallback is paid for exactly once
    assert store[(GA._SERVICE, GA._ACCOUNT)] == "ghp_legacy"


def test_keychain_prefers_new_name():
    store = {(GA._SERVICE, GA._ACCOUNT): "ghp_new",
             (GA._LEGACY_SERVICE, GA._ACCOUNT): "ghp_stale"}
    assert _with_fake_keyring(store, GA.get_token) == "ghp_new"


def test_keychain_no_token_anywhere():
    assert _with_fake_keyring({}, GA.get_token) is None


def test_clear_token_removes_legacy_too():
    """Disconnect must actually disconnect. Clearing only the new name would let
    get_token() resurrect the legacy token on the very next call."""
    store = {(GA._SERVICE, GA._ACCOUNT): "a",
             (GA._LEGACY_SERVICE, GA._ACCOUNT): "b"}
    _with_fake_keyring(store, GA.clear_token)
    assert store == {}
    assert _with_fake_keyring(store, GA.get_token) is None


# --- 3. per-repo block files ------------------------------------------------ #
def test_block_reads_new_name():
    d = tempfile.mkdtemp()
    try:
        open(os.path.join(d, ".orrery.json"), "w").write(json.dumps({"thesis": "new"}))
        assert R.read_block(d)["thesis"] == "new"
    finally:
        shutil.rmtree(d, ignore_errors=True)


def test_block_still_reads_legacy_name():
    """These files live in the USER's repos — we told people to write them, so
    2.0 can't stop reading them."""
    d = tempfile.mkdtemp()
    try:
        open(os.path.join(d, ".mission-control.json"), "w").write(
            json.dumps({"thesis": "legacy"}))
        assert R.read_block(d)["thesis"] == "legacy"
    finally:
        shutil.rmtree(d, ignore_errors=True)


def test_block_new_name_wins_over_legacy():
    d = tempfile.mkdtemp()
    try:
        open(os.path.join(d, ".orrery.json"), "w").write(json.dumps({"thesis": "new"}))
        open(os.path.join(d, ".mission-control.json"), "w").write(
            json.dumps({"thesis": "legacy"}))
        assert R.read_block(d)["thesis"] == "new"
    finally:
        shutil.rmtree(d, ignore_errors=True)


def test_block_yaml_both_spellings():
    for name, want in ((".orrery.yml", "y-new"), (".mission-control.yml", "y-old")):
        d = tempfile.mkdtemp()
        try:
            open(os.path.join(d, name), "w").write(f"thesis: {want}\n")
            assert R.read_block(d)["thesis"] == want
        finally:
            shutil.rmtree(d, ignore_errors=True)


def test_block_frontmatter_both_keys():
    for key, want in (("orrery", "fm-new"), ("mission-control", "fm-old")):
        d = tempfile.mkdtemp()
        try:
            open(os.path.join(d, "CLAUDE.md"), "w").write(
                f"---\n{key}:\n  thesis: {want}\n---\n# body\n")
            assert R.read_block(d)["thesis"] == want
        finally:
            shutil.rmtree(d, ignore_errors=True)


def test_block_absent_is_empty():
    d = tempfile.mkdtemp()
    try:
        assert R.read_block(d) == {}
    finally:
        shutil.rmtree(d, ignore_errors=True)


if __name__ == "__main__":
    fails = 0
    for fn in sorted(k for k in list(globals()) if k.startswith("test_")):
        try:
            globals()[fn]()
            print(f"ok   {fn}")
        except AssertionError as e:
            print(f"FAIL {fn}: {e}")
            fails += 1
    sys.exit(1 if fails else 0)
