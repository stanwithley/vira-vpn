# services/xray_service.py
import json
import os
import re
import shutil
import subprocess
import tempfile
import uuid
from typing import Tuple, Optional

XRAY_CONFIG_PATH = os.getenv("XRAY_CONFIG_PATH", "/usr/local/etc/xray/config.json")
XRAY_SERVICE_NAME = os.getenv("XRAY_SERVICE_NAME", "xray")
XRAY_DOMAIN = os.getenv("XRAY_DOMAIN", "127.0.0.1")
XRAY_WS_PATH = os.getenv("XRAY_WS_PATH", "/ws8081")
XRAY_PORT = int(os.getenv("XRAY_PORT", "8081"))
XRAY_SECURITY = os.getenv("XRAY_SECURITY", "none")  # none | tls | reality

INBOUND_TAG = "vless-ws"


# ---------- File IO helpers ----------
def _assert_paths():
    if not os.path.exists(XRAY_CONFIG_PATH):
        raise FileNotFoundError(f"XRAY_CONFIG_PATH not found: {XRAY_CONFIG_PATH}")
    if not os.access(XRAY_CONFIG_PATH, os.R_OK):
        raise PermissionError(f"No read permission for {XRAY_CONFIG_PATH}")
    # we will write atomically using os.replace; check dir permission
    cfg_dir = os.path.dirname(XRAY_CONFIG_PATH) or "."
    if not os.access(cfg_dir, os.W_OK):
        # write might still work via sudo tee if you choose that route,
        # but for direct write we need dir permission
        pass


def _load_config() -> dict:
    _assert_paths()
    with open(XRAY_CONFIG_PATH, "r") as f:
        return json.load(f)


def _save_config(cfg: dict):
    """Atomic write + lightweight backup to avoid corrupting config.json."""
    cfg_dir = os.path.dirname(XRAY_CONFIG_PATH) or "."
    backup = XRAY_CONFIG_PATH + ".bak"
    # best-effort backup
    if os.path.exists(XRAY_CONFIG_PATH):
        try:
            shutil.copy2(XRAY_CONFIG_PATH, backup)
        except Exception:
            pass

    fd, tmp = tempfile.mkstemp(dir=cfg_dir, prefix=".xraycfg_", suffix=".json")
    try:
        with os.fdopen(fd, "w") as f:
            json.dump(cfg, f, ensure_ascii=False, indent=2)
        os.replace(tmp, XRAY_CONFIG_PATH)
    finally:
        if os.path.exists(tmp):
            try:
                os.remove(tmp)
            except Exception:
                pass


def _restart_xray():
    """Restart Xray via systemd. Requires sudoers rule if non-root."""
    try:
        subprocess.run(
            ["sudo", "systemctl", "restart", XRAY_SERVICE_NAME],
            check=True,
            capture_output=True,
            text=True,
        )
    except subprocess.CalledProcessError as e:
        msg = e.stderr.strip() or e.stdout.strip() or str(e)
        raise RuntimeError(f"Failed to restart {XRAY_SERVICE_NAME}: {msg}")


# ---------- Inbound helpers ----------
def _safe_tag(s: str) -> str:
    # make a clean tag for URL fragment and client email label
    return re.sub(r"[^A-Za-z0-9._-]+", "_", s)


def _find_vless_ws_inbound(cfg: dict) -> Optional[dict]:
    # 1) by tag
    for ib in cfg.get("inbounds", []):
        if ib.get("tag") == INBOUND_TAG:
            return ib
    # 2) by protocol/network
    for ib in cfg.get("inbounds", []):
        if ib.get("protocol") == "vless" and ib.get("streamSettings", {}).get("network") == "ws":
            return ib
    return None


def _ensure_vless_ws_inbound(cfg: dict):
    ib = _find_vless_ws_inbound(cfg)
    if ib:
        return
    cfg.setdefault("inbounds", []).append({
        "tag": INBOUND_TAG,
        "port": XRAY_PORT,
        "protocol": "vless",
        "settings": {
            "clients": [],
            "decryption": "none"
        },
        "streamSettings": {
            "network": "ws",
            "security": XRAY_SECURITY,  # none | tls | reality
            "wsSettings": {"path": XRAY_WS_PATH}
        }
    })


def _build_vless_ws_link(uuid_str: str, email: str) -> str:
    host = XRAY_DOMAIN
    path = XRAY_WS_PATH
    port = XRAY_PORT
    name = _safe_tag(email)
    # Standard VLESS WS URL
    params = f"type=ws&path={path}&encryption=none&security={XRAY_SECURITY}"
    return f"vless://{uuid_str}@{host}:{port}?{params}#{name}"


# ---------- Public API ----------
def add_client(email: str) -> Tuple[str, str]:
    """
    Add (or reuse) a client to VLESS/WS inbound and return (uuid, vless_link).
    Idempotent per email: if email exists, returns existing client's link.
    """
    cfg = _load_config()
    _ensure_vless_ws_inbound(cfg)

    uid = str(uuid.uuid4())
    ib = _find_vless_ws_inbound(cfg)
    if not ib:
        raise RuntimeError("VLESS/WS inbound not found or failed to create.")

    clients = ib.setdefault("settings", {}).setdefault("clients", [])

    # reuse existing by email
    for c in clients:
        if c.get("email") == email:
            link = _build_vless_ws_link(c["id"], email)
            return c["id"], link

    clients.append({"id": uid, "email": email})

    _save_config(cfg)
    _restart_xray()
    return uid, _build_vless_ws_link(uid, email)


def remove_client(email: str) -> bool:
    """
    Remove client by email from VLESS/WS inbound. Returns True if changed.
    """
    cfg = _load_config()
    ib = _find_vless_ws_inbound(cfg)
    if not ib:
        return False

    clients = ib.setdefault("settings", {}).setdefault("clients", [])
    before = len(clients)
    clients[:] = [c for c in clients if c.get("email") != email]
    changed = len(clients) != before

    if changed:
        _save_config(cfg)
        _restart_xray()
    return changed
