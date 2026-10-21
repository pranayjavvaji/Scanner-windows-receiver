#!/usr/bin/env python3
"""BarScan Receiver - types barcodes sent from the BarScan phone app
wherever your cursor is (just like a hardware barcode scanner)."""
import argparse, hmac, json, os, queue, secrets, socket, sys, threading, time
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

VERSION = "1.0.0"
APP_DIR = os.path.dirname(sys.executable if getattr(sys, "frozen", False) else os.path.abspath(__file__))
CONFIG_PATH = os.path.join(APP_DIR, "config.json")
DEFAULTS = {
    "port": 8765,
    "token": "",
    "suffix": "enter",        # enter | tab | none  (key pressed after every scan)
    "mode": "type",           # type | clipboard    (clipboard = paste with Ctrl+V)
    "type_interval": 0.005,   # seconds between keystrokes
    "bulk_countdown": 3,      # seconds to click your target window before bulk typing
    "bulk_delay": 0.15,       # pause between items in bulk sends
    "require_token": True,
}
MAX_ITEMS, MAX_LEN = 5000, 500


def load_config():
    cfg = dict(DEFAULTS)
    if os.path.exists(CONFIG_PATH):
        try:
            with open(CONFIG_PATH, encoding="utf-8") as f:
                cfg.update(json.load(f))
        except Exception as e:
            print(f"[warn] could not read config.json: {e}")
    return cfg


def save_config(cfg):
    with open(CONFIG_PATH, "w", encoding="utf-8") as f:
        json.dump(cfg, f, indent=2)


def local_ips():
    ips = []
    try:
        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        s.connect(("10.255.255.255", 1))
        ips.append(s.getsockname()[0])
        s.close()
    except Exception:
        pass
    try:
        for ip in socket.gethostbyname_ex(socket.gethostname())[2]:
            if ip not in ips and not ip.startswith("127."):
                ips.append(ip)
    except Exception:
        pass
    return ips or ["127.0.0.1"]


class Typer:
    def __init__(self, dry):
        self.dry, self.pg, self.clip = dry, None, None
        if dry:
            return
        import pyautogui
        pyautogui.FAILSAFE = False
        pyautogui.PAUSE = 0
        self.pg = pyautogui
        try:
            import pyperclip
            self.clip = pyperclip
        except ImportError:
            pass

    def _paste(self, text):
        old = None
        try:
            old = self.clip.paste()
        except Exception:
            pass
        self.clip.copy(text)
        time.sleep(0.05)
        self.pg.hotkey("ctrl", "v")
        time.sleep(0.15)
        if old is not None:
            try:
                self.clip.copy(old)
            except Exception:
                pass

    def type_item(self, text, suffix, mode, interval):
        text = text.replace("\r", " ").replace("\n", " ")
        if self.dry:
            print(f"   [dry-run] would type {text!r} + {suffix}")
            return
        if self.clip and (mode == "clipboard" or not text.isascii()):
            self._paste(text)
        else:
            parts = text.split("\t")
            for i, p in enumerate(parts):
                if p:
                    self.pg.write(p, interval=interval)
                if i < len(parts) - 1:
                    self.pg.press("tab")
        if suffix in ("enter", "tab"):
            self.pg.press(suffix)


def make_handler(cfg, jobs):
    class H(BaseHTTPRequestHandler):
        server_version = "BarScanReceiver/" + VERSION

        def log_message(self, *a):
            pass

        def _send(self, code, obj):
            body = json.dumps(obj).encode()
            self.send_response(code)
            self.send_header("Content-Type", "application/json")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)

        def _authed(self):
            if not cfg["require_token"]:
                return True
            return hmac.compare_digest(self.headers.get("X-Token", ""), cfg["token"])

        def do_GET(self):
            if self.path.startswith("/ping"):
                return self._send(200, {"ok": True, "app": "barscan", "name": socket.gethostname(),
                                        "version": VERSION, "auth": cfg["require_token"],
                                        "authed": self._authed()})
            self._send(404, {"ok": False, "error": "not found"})

        def do_POST(self):
            if not self._authed():
                return self._send(401, {"ok": False, "error": "bad token"})
            try:
                n = int(self.headers.get("Content-Length", 0))
                data = json.loads(self.rfile.read(n) or b"{}")
            except Exception:
                return self._send(400, {"ok": False, "error": "bad json"})
            suffix = data.get("suffix", cfg["suffix"])
            if suffix not in ("enter", "tab", "none"):
                suffix = cfg["suffix"]
            if self.path == "/type":
                text = str(data.get("text", ""))[:MAX_LEN]
                if not text:
                    return self._send(400, {"ok": False, "error": "empty"})
                jobs.put({"items": [text], "suffix": suffix, "countdown": 0, "delay": 0})
                print(f"[scan] {text!r}")
                return self._send(200, {"ok": True, "queued": 1})
            if self.path == "/bulk":
                items = [str(x)[:MAX_LEN] for x in data.get("items", []) if str(x)][:MAX_ITEMS]
                if not items:
                    return self._send(400, {"ok": False, "error": "empty"})
                cd = int(data.get("countdown", cfg["bulk_countdown"]))
                delay = float(data.get("delay", cfg["bulk_delay"]))
                jobs.put({"items": items, "suffix": suffix, "countdown": max(0, min(cd, 30)),
                          "delay": max(0.0, min(delay, 5.0))})
                print(f"[bulk] {len(items)} items queued")
                return self._send(200, {"ok": True, "queued": len(items), "countdown": cd})
            self._send(404, {"ok": False, "error": "not found"})

    return H


def worker(jobs, typer, cfg):
    while True:
        job = jobs.get()
        try:
            for s in range(job["countdown"], 0, -1):
                print(f"   typing starts in {s}... click your target field now")
                time.sleep(1)
            for t in job["items"]:
                typer.type_item(t, job["suffix"], cfg["mode"], cfg["type_interval"])
                if job["delay"]:
                    time.sleep(job["delay"])
        except Exception as e:
            print(f"[error] typing failed: {e}")


def show_qr(payload, open_image):
    try:
        import qrcode
        qr = qrcode.QRCode(border=1)
        qr.add_data(payload)
        qr.make(fit=True)
        qr.print_ascii(invert=True)
        path = os.path.join(APP_DIR, "pairing_qr.png")
        qr.make_image().save(path)
        print(f"(QR also saved to {path})")
        if open_image and hasattr(os, "startfile"):
            os.startfile(path)
    except Exception as e:
        print(f"[warn] QR unavailable ({e}); enter the details manually in the app.")


def main():
    ap = argparse.ArgumentParser(description="BarScan receiver")
    ap.add_argument("--port", type=int)
    ap.add_argument("--suffix", choices=["enter", "tab", "none"])
    ap.add_argument("--mode", choices=["type", "clipboard"])
    ap.add_argument("--reset-token", action="store_true")
    ap.add_argument("--qr-image", action="store_true", help="open the pairing QR as an image")
    ap.add_argument("--dry-run", action="store_true", help="print instead of typing (for testing)")
    a = ap.parse_args()
    try:
        sys.stdout.reconfigure(encoding="utf-8")
    except Exception:
        pass

    cfg = load_config()
    for k in ("port", "suffix", "mode"):
        if getattr(a, k) is not None:
            cfg[k] = getattr(a, k)
    if a.reset_token or not cfg["token"]:
        cfg["token"] = secrets.token_hex(4)
    save_config(cfg)

    ips = local_ips()
    payload = json.dumps({"app": "barscan", "n": socket.gethostname(), "h": ips[0],
                          "p": cfg["port"], "t": cfg["token"]}, separators=(",", ":"))
    print(f"\n=== BarScan Receiver v{VERSION} ===")
    print(f"Address : {ips[0]}:{cfg['port']}" + (f"   (other: {', '.join(ips[1:])})" if len(ips) > 1 else ""))
    print(f"Token   : {cfg['token']}")
    print(f"Mode    : {cfg['mode']}, after each scan press: {cfg['suffix']}\n")
    print("In the app: Devices > Pair via QR, then scan this code:\n")
    show_qr(payload, a.qr_image)
    print("\nListening... click into any text field and scan. Ctrl+C to quit.\n")

    jobs = queue.Queue()
    typer = Typer(a.dry_run)
    threading.Thread(target=worker, args=(jobs, typer, cfg), daemon=True).start()
    try:
        ThreadingHTTPServer(("0.0.0.0", cfg["port"]), make_handler(cfg, jobs)).serve_forever()
    except OSError as e:
        print(f"[error] cannot listen on port {cfg['port']}: {e}")
        input("Press Enter to exit")
    except KeyboardInterrupt:
        print("bye")


if __name__ == "__main__":
    main()
