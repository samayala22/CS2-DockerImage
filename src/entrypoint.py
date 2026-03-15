#!/usr/bin/env python3

import os, subprocess, pathlib, random
import plugins
import configs

CS2_ROOT = pathlib.Path("/home/steam/cs2")
WORKSHOP_MAPS = ["3070194623", "3121168339", "3102712799", "3162361624", "3374560468", "3160291769", "3344417199", "3250581189", "3082213334", "3104579274", "3514400945", "3540061470", "3429375699", "3164403123", "3534437146", "3434238689", "3428669060", "3490455192", "3353950265", "3250581189"]

STEAMCMD_DIR = pathlib.Path("/home/steam/steamcmd")

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
    cmd = [str(STEAMCMD_DIR / "steamcmd.sh"), "+force_install_dir", str(CS2_ROOT), "+login", "anonymous", "+app_update", "730", "+quit"]
    subprocess.run(cmd, check=True)

def server_start():
    cmd = [
        str(CS2_ROOT / "game/cs2.sh"),
        "--graphics-provider", "", "--", "-dedicated", "-port", os.environ["PORT"], "-maxplayers", "32", "-usercon",
        "+sv_setsteamaccount", os.environ["GSLT"],
        "+exec", "cs2kz.cfg", "+map", "de_dust2", "+host_workshop_map", random.choice(WORKSHOP_MAPS)
    ]
    subprocess.run(cmd, check=True)

def main():
    print("Starting management script...")
    ensure_steamcmd()
    setup_steam_symlink()
    server_update()
    plugins.run()
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