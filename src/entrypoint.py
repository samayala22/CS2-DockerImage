#!/usr/bin/env python3

import os, subprocess, pathlib
import plugins
import configs

CS2_ROOT = pathlib.Path("/home/steam/cs2")

def setup_steam_symlink():
    steam_dir = pathlib.Path("/home/steam/.steam")
    if steam_dir.exists(): return
    steam_dir.mkdir(exist_ok=True)
    sdk_link = steam_dir / "sdk64"
    os.symlink("/opt/steamcmd/linux64", sdk_link)

def server_update():
    cmd = ["steamcmd.sh", "+force_install_dir", str(CS2_ROOT), "+login", "anonymous", "+app_update", "730", "+quit"]
    subprocess.run(cmd)

def server_start():
    cmd = [
        str(CS2_ROOT / "game/cs2.sh"),
        "--graphics-provider", "", "--", "-dedicated", "-port", os.getenv("PORT"), "-maxplayers", "32",
        "+sv_setsteamaccount", os.getenv("GSLT"),
        "+exec", "cs2kz.cfg", "+map", "de_dust2", "+host_workshop_map", "3121168339"
    ]
    subprocess.run(cmd)

def main():
    print("Starting kz-server management script...")
    setup_steam_symlink()
    server_update()
    plugins.run()
    configs.run()
    server_start()

if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print("\nServer stopped by user.\n")
    except Exception as e:
        import traceback
        traceback.print_exc()