#!/usr/bin/env python3
import pathlib

CS2_ROOT = pathlib.Path("/home/steam/cs2")
SERVER_CONFIG_DIR = pathlib.Path("/server-config")
STEAMCMD_DIR = pathlib.Path("/home/steam/steamcmd")
CS2_GAME_DIR = CS2_ROOT / "game" / "csgo"

PLUGINS_FILE = SERVER_CONFIG_DIR / "plugins.json"
CONFIGS_FILE = SERVER_CONFIG_DIR / "configs.json"
