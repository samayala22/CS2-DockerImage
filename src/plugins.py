#!/usr/bin/env python3
from __future__ import annotations

import os
import pathlib
import shutil
import requests
from urllib.parse import urljoin
import helpers
import json

CS2_ROOT = pathlib.Path("/home/steam/cs2")
SERVER_CONFIG_DIR = pathlib.Path("/server-config")
CS2_DIR = CS2_ROOT / "game" / "csgo"
PLUGINS_FILE = SERVER_CONFIG_DIR / "plugins.json"

def load_plugins() -> list[dict]:
    """Load plugins configuration from plugins.json."""
    with open(PLUGINS_FILE, "r") as f:
        return json.load(f)

def save_plugins(plugins: list[dict]):
    """Save plugins configuration to plugins.json."""
    with open(PLUGINS_FILE, "w") as f:
        json.dump(plugins, f, indent=4)

def match_asset(name: str, pattern: str) -> bool:
    """Match asset name against a pattern with wildcard support."""
    if "*" in pattern:
        parts = pattern.split("*")
        return all(p in name for p in parts if p)
    return pattern in name

def download_and_extract(url: str, destination: pathlib.Path, depth: int = 0) -> pathlib.Path | None:
    """Download archive and extract to destination with optional depth handling."""
    try:
        fp = helpers.fetch(url, destination)
    except Exception as e:
        print(f"Failed to download: {e}")
        return None
    
    # extract to temp directory first if depth > 0
    if depth > 0:
        extract_dir = destination / f"_temp_extract_{fp.stem}"
        extract_dir.mkdir(exist_ok=True)
        shutil.unpack_archive(fp, extract_dir)
        fp.unlink()
        
        # find the n-th depth folder and copy contents
        target = extract_dir
        for _ in range(depth):
            subdirs = [d for d in target.iterdir() if d.is_dir()]
            if subdirs:
                target = subdirs[0]
            else:
                break
        
        # copy contents to destination
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

def fetch_mmsdrop_latest(plugin: dict) -> tuple[str, str] | None:
    """Fetch latest tag and download url from mms alliedmods drop."""
    base_url = "https://mms.alliedmods.net/mmsdrop/2.0/"
    marker = plugin["asset"]
    
    response = requests.get(urljoin(base_url, marker))
    if not response.ok:
        print(f"Failed to fetch metamod marker: {response.status_code}")
        return None
    
    name = response.text.strip()
    tag = name.split("-")[2]  # extract version from filename
    url = urljoin(base_url, name)
    
    return (tag, url)

def fetch_github_latest(plugin: dict, token: str) -> tuple[str, str] | None:
    """Fetch latest tag and download url from github releases."""
    owner, repo = plugin["name"].split("/")
    asset_pattern = plugin["asset"]
    
    req_url = f"https://api.github.com/repos/{owner}/{repo}/releases/latest"
    headers = {"Authorization": f"Bearer {token}"} if token else {}
    
    response = requests.get(req_url, headers=headers)
    if not response.ok:
        print(f"Failed to fetch latest release for {repo}: {response.status_code}")
        return None
    
    data = response.json()
    tag = data["tag_name"]
    
    # find matching asset
    for asset in data["assets"]:
        if match_asset(asset["name"], asset_pattern):
            return (tag, asset["browser_download_url"])
    
    print(f"Failed to match asset pattern '{asset_pattern}' in {repo} release {tag}")
    return None

def update_plugin(plugin: dict, token: str) -> bool:
    """Update a single plugin based on its origin."""
    name = plugin["name"]
    origin = plugin.get("origin", "github")
    old_tag = plugin["tag"]
    
    # fetch latest release info
    if origin == "mmsdrop":
        result = fetch_mmsdrop_latest(plugin)
    elif origin == "github":
        result = fetch_github_latest(plugin, token)
    else:
        print(f"Unknown origin: {origin}")
        return False
    
    if result is None:
        return False
    
    tag, url = result
    
    # check if update needed
    if old_tag == tag:
        print(f"{name} is up to date ({tag})")
        return False
    
    # download and extract
    print(f"Updating {name} to {tag}")
    destination = CS2_ROOT / pathlib.Path(plugin["destination"].replace("root/", ""))
    
    if download_and_extract(url, destination, plugin.get("depth", 0)):
        plugin["tag"] = tag
        print(f"Updated {name} to {tag}")
        return True
    
    return False

def run():
    """Main function to update all plugins."""
    print("Checking for plugin updates...")
    token = os.getenv("GITHUB_APIKEY", "")
    plugins = load_plugins()
    
    updated = False
    for plugin in plugins:
        if update_plugin(plugin, token):
            updated = True
    
    if updated:
        save_plugins(plugins)
    
    return 0

if __name__ == "__main__":
    run()