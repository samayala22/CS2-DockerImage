#!/usr/bin/env python3
from __future__ import annotations

import os
import pathlib
import shutil
import requests
import json
from paths import CS2_ROOT, PLUGINS_FILE


def load_plugins() -> list[dict]:
    with open(PLUGINS_FILE, "r") as f:
        return json.load(f)


def save_plugins(plugins: list[dict]):
    with open(PLUGINS_FILE, "w") as f:
        json.dump(plugins, f, indent=4)


def match_asset(name: str, pattern: str) -> bool:
    if "*" in pattern:
        parts = pattern.split("*")
        return all(p in name for p in parts if p)
    return pattern in name


def _download_file(url: str, dest_dir: pathlib.Path) -> pathlib.Path:
    fp = dest_dir / url.split("/")[-1]
    tmp = fp.with_suffix(fp.suffix + ".tmp")
    with requests.get(url, stream=True) as r:
        r.raise_for_status()
        with open(tmp, "wb") as f:
            for chunk in r.iter_content(chunk_size=16384):
                f.write(chunk)
    tmp.replace(fp)
    return fp


def download_and_extract(url: str, destination: pathlib.Path, depth: int = 0) -> pathlib.Path | None:
    try:
        fp = _download_file(url, destination)
    except Exception as e:
        print(f"Failed to download: {e}")
        return None

    if depth > 0:
        extract_dir = destination / f"_temp_extract_{fp.stem}"
        extract_dir.mkdir(exist_ok=True)
        shutil.unpack_archive(fp, extract_dir)
        fp.unlink()

        target = extract_dir
        for _ in range(depth):
            subdirs = [d for d in target.iterdir() if d.is_dir()]
            if subdirs:
                target = subdirs[0]
            else:
                break

        for item in target.iterdir():
            dest_item = destination / item.name
            if item.is_dir():
                shutil.copytree(item, dest_item, dirs_exist_ok=True)
            else:
                shutil.copy2(item, dest_item)

        shutil.rmtree(extract_dir)
    else:
        shutil.unpack_archive(fp, destination)
        fp.unlink()

    return destination


def fetch_github_release(plugin: dict, token: str) -> tuple[str, str, str | None] | None:
    """Fetch the latest matching release from GitHub.

    Returns (tag, download_url, new_etag) or None if unchanged / failed.
    Uses ETag / If-None-Match for conditional requests to avoid burning API rate limit.
    """
    owner, repo = plugin["name"].split("/")
    asset_pattern = plugin["asset"]

    url = f"https://api.github.com/repos/{owner}/{repo}/releases?per_page=1"
    headers = {"Authorization": f"Bearer {token}"} if token else {}

    cached_etag = plugin.get("etag")
    if cached_etag:
        headers["If-None-Match"] = cached_etag

    response = requests.get(url, headers=headers)

    if response.status_code == 304:
        print(f"{plugin['name']} release unchanged (cached)")
        return None

    if not response.ok:
        print(f"Failed to fetch releases for {repo}: {response.status_code}")
        return None

    new_etag = response.headers.get("ETag")

    for release in response.json():
        if release.get("draft"):
            continue
        tag = release["tag_name"]
        if "beta" in tag.lower(): 
            continue
        for asset in release.get("assets", []):
            if match_asset(asset["name"], asset_pattern):
                return (tag, asset["browser_download_url"], new_etag)

    print(f"Failed to match asset pattern '{asset_pattern}' in {repo} releases")
    return None


def update_plugin(plugin: dict, token: str) -> dict | None:
    """Check and apply an update for a single plugin.

    Returns an updated plugin dict (with new tag and/or last_modified) on success,
    or None if nothing changed.
    """
    name = plugin["name"]

    result = fetch_github_release(plugin, token)
    if result is None:
        return None

    tag, url, new_etag = result

    if plugin.get("tag") == tag:
        print(f"{name} is up to date ({tag})")
        if new_etag and new_etag != plugin.get("etag"):
            return {**plugin, "etag": new_etag}
        return None

    print(f"Updating {name} to {tag}")
    destination = CS2_ROOT / pathlib.Path(plugin["destination"].replace("root/", ""))

    if download_and_extract(url, destination, plugin.get("depth", 0)) is None:
        return None

    print(f"Updated {name} to {tag}")
    return {**plugin, "tag": tag, "etag": new_etag}


def run():
    print("Checking for plugin updates...")
    token = os.getenv("GITHUB_APIKEY", "")
    plugins = load_plugins()

    updated_plugins = [update_plugin(p, token) or p for p in plugins]
    save_plugins(updated_plugins)


if __name__ == "__main__":
    run()