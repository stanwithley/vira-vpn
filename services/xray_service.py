# services/xray_service.py
import json
import os
import re
import shutil
import subprocess
import tempfile
import uuid
from typing import Tuple, Optional
from urllib.parse import quote

# ===== Settings (env) =====
XRAY_CONFIG_PATH = os.getenv("XRAY_CONFIG_PATH", "/usr/local/etc/xray/config.json")
XRAY_SERVICE_NAME = os.getenv("XRAY_SERVICE_NAME", "xray")

# لینک‌سازی VLESS/WS
XRAY_DOMAIN = os.getenv("XRAY_DOMAIN", "127.0.0.1")
XRAY_WS_PATH = os.getenv("XRAY_WS_PATH", "/ws8081")
XRAY_PORT = int(os.getenv("XRAY_PORT", "8081"))
XRAY_SECURITY = os.getenv("XRAY_SECURITY", "none")  # none | tls | reality

# Runtime API
XRAY_BIN = os.getenv("XRAY_BIN", "/usr/local/bin/xray")
XRAY_API_ADDR = os.getenv("XRAY_API_ADDR", "127.0.0.1:10085")
INBOUND_TAG = os.getenv("XRAY_INBOUND_TAG", "vless-ws")  # باید در config به inbound 8081 داده شده باشد (tag)


# ---------- File IO helpers ----------
def _test_config(path: str) -> None:
    """xray -test -config <path>؛ خطا بده اگر نامعتبر بود."""
    p = subprocess.run(
        [XRAY_BIN, "-test", "-config", path],
        capture_output=True, text=True
    )
    if p.returncode != 0:
        msg = (p.stderr or p.stdout or "").strip()
        raise RuntimeError(f"xray -test failed: {msg}")


def _apply_config_safely(new_cfg: dict) -> None:
    """
    کانفیگ جدید را در فایل موقت می‌نویسد، تست می‌کند،
    اگر OK بود اتمیک جایگزین می‌کند و سپس reload می‌زند.
    اگر هر مرحله‌ای خطا داشت، کانفیگ قبلی برمی‌گردد.
    """
    cfg_dir = os.path.dirname(XRAY_CONFIG_PATH) or "."
    backup = XRAY_CONFIG_PATH + ".bak"

    # 1) نوشتن موقت
    fd, tmp = tempfile.mkstemp(dir=cfg_dir, prefix=".xraycfg_", suffix=".json")
    os.close(fd)
    try:
        with open(tmp, "w") as f:
            json.dump(new_cfg, f, ensure_ascii=False, indent=2)

        # 2) تست
        _test_config(tmp)

        # 3) بکاپ و جایگزینی اتمیک
        if os.path.exists(XRAY_CONFIG_PATH):
            try:
                shutil.copy2(XRAY_CONFIG_PATH, backup)
            except Exception:
                pass
        os.replace(tmp, XRAY_CONFIG_PATH)

        # 4) ری‌لود (HUP)؛ اگر نشد، ری‌استارت
        try:
            subprocess.run(["sudo", "systemctl", "reload", XRAY_SERVICE_NAME],
                           check=True, capture_output=True, text=True)
        except subprocess.CalledProcessError:
            subprocess.run(["sudo", "systemctl", "restart", XRAY_SERVICE_NAME],
                           check=True, capture_output=True, text=True)

    except Exception as e:
        # اگر هرکدام شکست خورد و فایل موقت هست پاک کن
        try:
            if os.path.exists(tmp):
                os.remove(tmp)
        finally:
            raise


def _assert_paths():
    if not os.path.exists(XRAY_CONFIG_PATH):
        raise FileNotFoundError(f"XRAY_CONFIG_PATH not found: {XRAY_CONFIG_PATH}")
    if not os.access(XRAY_CONFIG_PATH, os.R_OK):
        raise PermissionError(f"No read permission for {XRAY_CONFIG_PATH}")
    cfg_dir = os.path.dirname(XRAY_CONFIG_PATH) or "."
    if not os.access(cfg_dir, os.W_OK):
        # ممکنه با sudo systemd مدیریت شه؛ اینجا فقط هشدار ذهنی
        pass


def _load_config() -> dict:
    _assert_paths()
    with open(XRAY_CONFIG_PATH, "r") as f:
        return json.load(f)


def _save_config(cfg: dict):
    """Atomic write + backup + chmod 0644 تا systemd بتونه بخونه."""
    cfg_dir = os.path.dirname(XRAY_CONFIG_PATH) or "."
    backup = XRAY_CONFIG_PATH + ".bak"
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
        try:
            os.chmod(XRAY_CONFIG_PATH, 0o644)
        except Exception:
            pass
    finally:
        if os.path.exists(tmp):
            try:
                os.remove(tmp)
            except Exception:
                pass


# ---------- systemd helpers ----------
def _restart_xray():
    try:
        subprocess.run(
            ["sudo", "systemctl", "restart", XRAY_SERVICE_NAME],
            check=True, capture_output=True, text=True,
        )
    except subprocess.CalledProcessError as e:
        msg = e.stderr.strip() or e.stdout.strip() or str(e)
        raise RuntimeError(f"Failed to restart {XRAY_SERVICE_NAME}: {msg}")


def _reload_xray():
    """ترجیح با reload برای حداقل قطعی؛ اگر نبود → restart."""
    try:
        subprocess.run(
            ["sudo", "systemctl", "reload", XRAY_SERVICE_NAME],
            check=True, capture_output=True, text=True,
        )
    except subprocess.CalledProcessError as e:
        try:
            subprocess.run(
                ["sudo", "systemctl", "restart", XRAY_SERVICE_NAME],
                check=True, capture_output=True, text=True,
            )
        except subprocess.CalledProcessError as e2:
            msg1 = e.stderr.strip() or e.stdout.strip() or str(e)
            msg2 = e2.stderr.strip() or e2.stdout.strip() or str(e2)
            raise RuntimeError(
                f"Failed to reload {XRAY_SERVICE_NAME}: {msg1}; restart fallback failed: {msg2}"
            )


# ---------- Inbound helpers (file mode) ----------
def _safe_tag(s: str) -> str:
    return re.sub(r"[^A-Za-z0-9._-]+", "_", s)


def _find_vless_ws_inbound(cfg: dict) -> Optional[dict]:
    for ib in cfg.get("inbounds", []):
        if ib.get("tag") == INBOUND_TAG:
            return ib
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
        "settings": {"clients": [], "decryption": "none"},
        "streamSettings": {
            "network": "ws",
            "security": XRAY_SECURITY,
            "wsSettings": {"path": XRAY_WS_PATH}
        }
    })


def _build_vless_ws_link(uuid_str: str, email: str) -> str:
    host = XRAY_DOMAIN
    path = XRAY_WS_PATH
    port = XRAY_PORT
    name = quote(email, safe="")
    params = f"type=ws&path={path}&encryption=none&security={XRAY_SECURITY}"
    return f"vless://{uuid_str}@{host}:{port}?{params}#{name}"


# ---------- Runtime API helpers ----------
def _xray_api(args: list[str]) -> subprocess.CompletedProcess:
    return subprocess.run(
        [XRAY_BIN, "api", *args],
        check=True, capture_output=True, text=True
    )


def _add_user_runtime(email: str, uuid_str: Optional[str] = None) -> str:
    """addUser روی هندلر runtime (بی‌قطعی). خروجی: لینک VLESS."""
    if not uuid_str:
        uuid_str = str(uuid.uuid4())
    user_obj = {"id": uuid_str, "email": email}
    _xray_api([
        "handler", "addUser",
        f"--server={XRAY_API_ADDR}",
        f"--tag={INBOUND_TAG}",
        f"--user={json.dumps(user_obj)}",
    ])
    return _build_vless_ws_link(uuid_str, email)


def _remove_user_runtime(email: str) -> bool:
    try:
        _xray_api([
            "handler", "removeUser",
            f"--server={XRAY_API_ADDR}",
            f"--tag={INBOUND_TAG}",
            f"--email={email}",
        ])
        return True
    except Exception:
        return False


# ---------- Public API ----------
def add_client(email: str) -> Tuple[str, str]:
    cfg = _load_config()
    _ensure_vless_ws_inbound(cfg)

    ib = _find_vless_ws_inbound(cfg)
    if not ib:
        raise RuntimeError("VLESS/WS inbound not found or failed to create.")

    clients = ib.setdefault("settings", {}).setdefault("clients", [])

    # اگر ایمیل وجود دارد، کانفیگ را دست نمی‌زنیم (بدون ری‌لود)
    for c in clients:
        if c.get("email") == email:
            link = _build_vless_ws_link(c["id"], email)
            return c["id"], link

    # افزودن کلاینت جدید
    uid = str(uuid.uuid4())
    clients.append({"id": uid, "email": email})

    # به‌صورت امن اعمال کن (تست + رول‌بک)
    _apply_config_safely(cfg)

    return uid, _build_vless_ws_link(uid, email)


def remove_client(email: str) -> bool:
    """
    حذف کاربر:
    1) سعی با Runtime API؛
    2) اگر نشد → از فایل حذف + reload.
    """
    if _remove_user_runtime(email):
        return True

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
        _reload_xray()
    return changed


# ---------- Stats (traffic per user) ----------
def _xray_api_stats_query(name: str) -> int:
    """
    xray api stats query --server=127.0.0.1:10085 --name 'user>>>EMAIL>>>traffic>>>uplink'
    خروجی برخی بیلدها «value: N» است؛ تبدیل به int می‌کنیم.
    """
    try:
        cmd = [XRAY_BIN, "api", "stats", "query", f"--server={XRAY_API_ADDR}", "--name", name]
        p = subprocess.run(cmd, check=True, capture_output=True, text=True)
        out = (p.stdout or "").strip()
        if out.startswith("value:"):
            out = out.split(":", 1)[1].strip()
        return int(out or "0")
    except Exception:
        return 0


def get_user_traffic_bytes(email: str) -> tuple[int, int, int]:
    """بایت‌های (uplink, downlink, total) برای یک ایمیل کاربر."""
    up = _xray_api_stats_query(f"user>>>{email}>>>traffic>>>uplink")
    dn = _xray_api_stats_query(f"user>>>{email}>>>traffic>>>downlink")
    return up, dn, up + dn
