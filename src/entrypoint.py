#!/usr/bin/env python3

import os, subprocess, pathlib, random
import requests
import plugins
import configs
from paths import CS2_ROOT, STEAMCMD_DIR, CS2_GAME_DIR

WORKSHOP_MAPS = ["3070194623", "3121168339", "3102712799", "3162361624", "3374560468", "3160291769", "3344417199", "3250581189", "3082213334", "3104579274", "3514400945", "3540061470", "3429375699", "3164403123", "3534437146", "3434238689", "3428669060", "3490455192", "3353950265", "3250581189"]


def fetch_random_map() -> str:
    try:
        response = requests.get("https://api.cs2kz.org/maps", timeout=10)
        response.raise_for_status()
        maps = response.json().get("values", [])
        if maps:
            return str(random.choice(maps)["workshop_id"])
    except Exception as e:
        print(f"Failed to fetch maps from API, falling back to hardcoded list: {e}")
    return random.choice(WORKSHOP_MAPS)


def ensure_steamcmd():
    """Install SteamCMD if missing (volume may overlay the image layer)."""
    if (STEAMCMD_DIR / "steamcmd.sh").exists():
        return
    STEAMCMD_DIR.mkdir(parents=True, exist_ok=True)
    subprocess.run(
        ["bash", "-c", f'curl -sqL "https://steamcdn-a.akamaihd.net/client/installer/steamcmd_linux.tar.gz" | tar zxvf - -C {STEAMCMD_DIR}'],
        check=True,
    )


def setup_steam_symlink():
    steam_dir = pathlib.Path("/home/steam/.steam")
    steam_dir.mkdir(exist_ok=True)
    sdk_link = steam_dir / "sdk64"
    target = STEAMCMD_DIR / "linux64"
    if sdk_link.is_symlink():
        if sdk_link.resolve() == target.resolve():
            return
        sdk_link.unlink()
    os.symlink(str(target), sdk_link)


def server_update():
    cmd = [str(STEAMCMD_DIR / "steamcmd.sh"), "+force_install_dir", str(CS2_ROOT), "+login", "anonymous", "+app_update", "730", "+validate", "+quit"]
    subprocess.run(cmd)


def remove_swiftly_vdf():
    swiftly_vdf = CS2_GAME_DIR / "addons" / "metamod" / "swiftlys2.vdf"
    if swiftly_vdf.exists():
        swiftly_vdf.unlink()
        print(f"Removed {swiftly_vdf}")


def server_start():
    cmd = [
        str(CS2_ROOT / "game/cs2.sh"),
        "--graphics-provider", "", "--", "-dedicated", "-port", os.environ["PORT"], "-maxplayers", "32", "-usercon",
        "+sv_setsteamaccount", os.environ["GSLT"],
        "+exec", "cs2kz.cfg", "+map", "de_dust2", "+host_workshop_map", fetch_random_map()
    ]
    subprocess.run(cmd)


def main():
    print("Starting management script...")
    ensure_steamcmd()
    setup_steam_symlink()
    server_update()
    plugins.run()
    remove_swiftly_vdf()
    configs.run()
    pathlib.Path("/tmp/server_started").touch()
    server_start()


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print("\nServer stopped by user.\n")
    except Exception as e:
        import traceback
        traceback.print_exc()