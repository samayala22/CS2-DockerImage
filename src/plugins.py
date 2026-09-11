#!/usr/bin/env python3
"""Plugin installer.

plugins.json is user-owned desired state and is never written to. Add
"version": "v1.2.3" to an entry to pin it; omit it to track the latest release.

What is actually installed (tag, the files it wrote, and the release-listing
ETag) lives separately in PLUGIN_STATE_FILE, so changing a pin is a real change
that triggers a reinstall.
"""
from __future__ import annotations

import json
import os
import pathlib
import shutil
import tempfile
from typing import Literal, NamedTuple

import requests

from paths import CS2_ROOT, PLUGINS_FILE, PLUGIN_STATE_FILE

GITHUB_API = "https://api.github.com"

# resolve_latest(): GitHub confirmed the release listing has not changed.
UNCHANGED = "unchanged"


class Release(NamedTuple):
    tag: str
    url: str
    etag: str | None


def load_plugins() -> list[dict]:
    with open(PLUGINS_FILE, "r") as f:
        return json.load(f)


def load_state() -> dict[str, dict]:
    """Load installed state. Missing or unreadable means "nothing installed"."""
    try:
        with open(PLUGIN_STATE_FILE, "r") as f:
            return json.load(f)
    except (FileNotFoundError, ValueError):
        return {}


def save_state(state: dict[str, dict]):
    tmp = PLUGIN_STATE_FILE.with_suffix(".json.tmp")
    with open(tmp, "w") as f:
        json.dump(state, f, indent=4, sort_keys=True)
    tmp.replace(PLUGIN_STATE_FILE)


# -----------------------------------------------------------------------------
# release resolution
# -----------------------------------------------------------------------------

def match_asset(name: str, pattern: str) -> bool:
    if "*" in pattern:
        parts = pattern.split("*")
        return all(p in name for p in parts if p)
    return pattern in name


def _auth(token: str) -> dict:
    return {"Authorization": f"Bearer {token}"} if token else {}


def _asset_url(release: dict, pattern: str) -> str | None:
    for asset in release.get("assets", []):
        if match_asset(asset["name"], pattern):
            return asset["browser_download_url"]
    return None


def resolve_pinned(plugin: dict, tag: str, token: str) -> Release | None:
    """Resolve an explicit tag. Skips the release listing, so no ETag involved."""
    name = plugin["name"]
    response = requests.get(f"{GITHUB_API}/repos/{name}/releases/tags/{tag}", headers=_auth(token))

    if not response.ok:
        print(f"{name}: failed to fetch pinned release '{tag}': {response.status_code}")
        return None

    url = _asset_url(response.json(), plugin["asset"])
    if url is None:
        print(f"{name}: no asset matching '{plugin['asset']}' in release {tag}")
        return None
    return Release(tag, url, None)


def resolve_latest(plugin: dict, etag: str | None, token: str) -> Release | Literal["unchanged"] | None:
    """Resolve the latest release. The ETag is only ever stored after a
    successful unpinned install, so a 304 means the install is current."""
    name = plugin["name"]
    channel = plugin.get("channel", "stable")
    
    headers = _auth(token)
    if etag:
        headers["If-None-Match"] = etag

    if channel == "stable":
        url = f"{GITHUB_API}/repos/{name}/releases/latest"
    else:
        url = f"{GITHUB_API}/repos/{name}/releases?per_page=1"
    
    response = requests.get(url, headers=headers)

    if response.status_code == 304:
        return UNCHANGED
    if not response.ok:
        print(f"{name}: failed to fetch releases: {response.status_code}")
        return None

    payload = response.json()
    for release in [payload] if channel == "stable" else payload:
        url = _asset_url(release, plugin["asset"])
        if url:
            return Release(release["tag_name"], url, response.headers.get("ETag"))

    print(f"{name}: no asset matching '{plugin['asset']}' in latest release")
    return None


# -----------------------------------------------------------------------------
# install / uninstall
# -----------------------------------------------------------------------------

def _download(url: str, dest_dir: pathlib.Path) -> pathlib.Path:
    fp = dest_dir / url.split("/")[-1]
    with requests.get(url, stream=True) as r:
        r.raise_for_status()
        with open(fp, "wb") as f:
            for chunk in r.iter_content(chunk_size=16384):
                f.write(chunk)
    return fp


def stage(url: str, workdir: pathlib.Path, depth: int) -> pathlib.Path:
    """Download and unpack `url`, returning the directory whose contents belong
    in the plugin destination. `depth` skips that many wrapper directories."""
    archive = _download(url, workdir)
    root = workdir / "extract"
    root.mkdir()
    shutil.unpack_archive(archive, root)
    archive.unlink()

    for _ in range(depth):
        subdirs = [d for d in root.iterdir() if d.is_dir()]
        if not subdirs:
            break
        root = subdirs[0]
    return root


def copy_into(src: pathlib.Path, destination: pathlib.Path) -> list[str]:
    """Copy the contents of `src` into `destination`, returning the written
    paths relative to CS2_ROOT."""
    files = []
    for item in sorted(src.rglob("*")):
        if item.is_dir():
            continue
        target = destination / item.relative_to(src)
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(item, target)
        files.append(target.relative_to(CS2_ROOT).as_posix())
    return files


def remove_files(rel_paths: list[str]):
    """Remove tracked files and any directory they leave empty. Only files we
    installed are touched, so configs the plugin generated at runtime survive."""
    root = CS2_ROOT.resolve()
    parents = set()

    for rel in rel_paths:
        path = (CS2_ROOT / rel).resolve()
        if path == root or not path.is_relative_to(root):
            print(f"Refusing to remove '{rel}': resolves outside {root}")
            continue
        path.unlink(missing_ok=True)
        parents.add(path.parent)

    for parent in sorted(parents, key=lambda p: len(p.parts), reverse=True):
        while parent != root and parent.is_dir():
            try:
                parent.rmdir()
            except OSError:
                break
            parent = parent.parent


def install(plugin: dict, release: Release, previous: list[str]) -> list[str] | None:
    """Install `release`, replacing `previous`. Returns the installed paths, or
    None if the download failed and nothing was touched."""
    destination = CS2_ROOT / pathlib.Path(plugin["destination"].replace("root/", ""))

    with tempfile.TemporaryDirectory(prefix=".plugin-staging-", dir=CS2_ROOT) as tmp:
        try:
            staged = stage(release.url, pathlib.Path(tmp), plugin.get("depth", 0))
        except Exception as e:
            # Stage first so a failed download leaves a working install alone.
            print(f"{plugin['name']}: failed to download or unpack {release.url}: {e}")
            return None

        remove_files(previous)
        destination.mkdir(parents=True, exist_ok=True)
        return copy_into(staged, destination)


# -----------------------------------------------------------------------------
# reconciliation
# -----------------------------------------------------------------------------

def files_present(rel_paths: list[str]) -> bool:
    return bool(rel_paths) and all((CS2_ROOT / p).exists() for p in rel_paths)


def reconcile(plugin: dict, entry: dict, token: str) -> dict:
    """Bring one plugin in line with the manifest, returning its state entry."""
    name = plugin["name"]
    pinned = plugin.get("version")

    if pinned:
        release = resolve_pinned(plugin, pinned, token)
    else:
        release = resolve_latest(plugin, entry.get("etag"), token)

    if release is None:
        return entry
    if release == UNCHANGED:
        print(f"{name} is up to date ({entry.get('tag')}, cached)")
        return entry

    files = entry.get("files") or []
    if entry.get("tag") == release.tag and files_present(files):
        print(f"{name} is up to date ({release.tag})")
        return {"tag": release.tag, "files": files, "etag": release.etag}

    print(f"{name}: {entry.get('tag') or 'nothing'} -> {release.tag}")
    files = install(plugin, release, files)
    if files is None:
        return entry

    print(f"{name}: installed {release.tag} ({len(files)} files)")
    return {"tag": release.tag, "files": files, "etag": release.etag}


def run():
    print("Checking for plugin updates...")
    token = os.getenv("GITHUB_APIKEY", "")
    manifest = load_plugins()
    state = load_state()
    new_state = {}
    for plugin in manifest:
        name = plugin["name"]
        try:
            new_state[name] = reconcile(plugin, state.get(name, {}), token)
        except Exception as e:
            print(f"{name}: failed: {e}")
            new_state[name] = state.get(name, {})

    for name, entry in state.items():
        if name not in new_state:
            print(f"Removing {name}")
            remove_files(entry.get("files") or [])

    save_state(new_state)


if __name__ == "__main__":
    run()
