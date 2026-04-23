#!/usr/bin/env python3
from __future__ import annotations

import os, re, pathlib, pyjson5, json

CS2_ROOT = pathlib.Path("/home/steam/cs2")
SERVER_CONFIG_DIR = pathlib.Path("/server-config")
CONFIGS_FILE = SERVER_CONFIG_DIR / "configs.json"

ENV_PATTERN = re.compile(r'\{env\.([^}]+)\}')

def load_configs() -> list[dict]:
    """Load configs from configs.json (strips // comments)."""
    with open(CONFIGS_FILE, "r") as f:
        content = f.read()
    return pyjson5.loads(content)

def substitute_env(value: str) -> str:
    """Replace {env.VAR_NAME} patterns with environment variable values."""
    def replacer(match):
        var_name = match.group(1)
        return os.getenv(var_name, "")
    return ENV_PATTERN.sub(replacer, value)

def substitute_env_recursive(obj):
    """Recursively substitute env vars in strings within dicts/lists."""
    if isinstance(obj, str):
        return substitute_env(obj)
    elif isinstance(obj, dict):
        return {k: substitute_env_recursive(v) for k, v in obj.items()}
    elif isinstance(obj, list):
        return [substitute_env_recursive(item) for item in obj]
    return obj

def atomic_write(path: pathlib.Path, content: str):
    """Write content to file atomically using a temp file."""
    tmp = path.with_suffix(path.suffix + '.tmp')
    with open(tmp, 'w') as f:
        f.write(content)
    tmp.replace(path)

# -----------------------------------------------------------------------------
# gi: replace entries between Game_LowViolence and Game csgo
# -----------------------------------------------------------------------------

def apply_gi(path: pathlib.Path, entries: dict):
    with open(path, 'r') as f:
        lines = f.readlines()

    start_prefix = "Game_LowViolence"
    end_pattern = "Game csgo"
    insert_idx = None
    end_idx = None

    for i, line in enumerate(lines):
        normalized_line = " ".join(line.split())

        if insert_idx is None and normalized_line.startswith(start_prefix):
            insert_idx = i + 1
            continue
        if insert_idx is not None and normalized_line == end_pattern:
            end_idx = i
            break

    if insert_idx is None:
        print(f"Pattern starting with '{start_prefix}' not found in {path}")
        return False

    if end_idx is None:
        print(f"Pattern '{end_pattern}' not found in {path}")
        return False

    entry_lines = [v + "\n" for v in entries.values()]

    lines[insert_idx:end_idx] = entry_lines
    atomic_write(path, ''.join(lines))
    print(f"Updated {path.name}")
    return True

# -----------------------------------------------------------------------------
# cfg: overwrite file with all entries (write mode)
# -----------------------------------------------------------------------------

def apply_cfg(path: pathlib.Path, entries: dict):
    lines = [f'{k} "{v}"\n' for k, v in entries.items()]
    atomic_write(path, ''.join(lines))
    print(f"Updated {path.name}")
    return True

# -----------------------------------------------------------------------------
# jsonc: parse (strip comments), update keys, write back
# -----------------------------------------------------------------------------

def apply_jsonc(path: pathlib.Path, entries: dict):
    with open(path, 'r') as f:
        content = f.read()

    data = pyjson5.loads(content)
        
    # update existing keys (replace entire value for each key)
    for k, v in entries.items():
        if k in data:
            data[k] = v
        else:
            print(f"Warning: key '{k}' not found in {path.name}")
    
    atomic_write(path, json.dumps(data, indent=4))
    print(f"Updated {path.name}")
    return True

# -----------------------------------------------------------------------------
# kv3: find "key" "value" patterns and replace value
# -----------------------------------------------------------------------------

def apply_kv3(path: pathlib.Path, entries: dict):
    with open(path, 'r') as f:
        content = f.read()
        
    def replace_kv3(content: str, key: str, value) -> str:
        if isinstance(value, dict):
            for k, v in value.items():
                content = replace_kv3(content, k, v)
            return content
        
        val_str = str(value) if not isinstance(value, str) else value
        # match "key" followed by whitespace and "value"
        pattern = rf'^(\s*"{re.escape(key)}"\s*)"[^"]*"'
        return re.sub(pattern, rf'\1"{val_str}"', content, count=1, flags=re.MULTILINE)
    
    for key, value in entries.items():
        content = replace_kv3(content, key, value)
    
    atomic_write(path, content)
    print(f"Updated {path.name}")
    return True

# -----------------------------------------------------------------------------
# ini / toml
# -----------------------------------------------------------------------------

def apply_ini(path: pathlib.Path, entries: dict):
    file_str = ""
    for section, value in entries.items():
        file_str += f'[{section}]\n'
        for key, val in value.items():
            if isinstance(val, str):
                val_str = f'"{val}"'
            elif isinstance(val, bool):
                val_str = "true" if val else "false"
            else:
                val_str = str(val)
            file_str += f'{key} = {val_str}\n'
        file_str += '\n'

    atomic_write(path, file_str)
    print(f"Updated {path.name}")
    return True

# -----------------------------------------------------------------------------
# main
# -----------------------------------------------------------------------------

FORMAT_HANDLERS = {
    "gi": apply_gi,
    "cfg": apply_cfg,
    "kv3": apply_kv3,
    "jsonc": apply_jsonc,
    "ini": apply_ini,
}

def apply_config(config: dict) -> bool:
    file_path = CS2_ROOT / pathlib.Path(config["file"].replace("root/", ""))
    if not file_path.exists():
        print(f"File not found: {file_path}")
        return False

    entries = substitute_env_recursive(config["entries"])
    
    fmt = config["format"]
    handler = FORMAT_HANDLERS.get(fmt)
    if handler is None:
        print(f"Unknown format: {fmt}")
        return False
    
    return handler(file_path, entries)

def run():
    print("Applying configurations...")
    configs = load_configs()
    for config in configs:
        apply_config(config)
    return 0

if __name__ == "__main__":
    run()