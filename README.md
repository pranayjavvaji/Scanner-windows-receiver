# BarScan Windows Receiver

A lightweight Windows keystroke receiver for the **BarScan** mobile app. 

When you scan barcodes on your phone, this receiver accepts them over your local Wi-Fi and types them wherever your cursor is (like an actual USB barcode scanner gun).

---

## Quick Start

### 1. Requirements
* Windows 10/11
* Python 3.9+ (make sure "Add python.exe to PATH" is checked during Python installation)

### 2. Setup
1. Open PowerShell or Command Prompt in this folder.
2. Install the required Python packages:
   ```cmd
   pip install -r requirements.txt
   ```
3. (First time only) Allow the port through Windows Firewall:
   * Right-click `allow_firewall.bat` and select **Run as Administrator**.

### 3. Run
Start the receiver:
```cmd
python receiver.py
```
* An **ASCII QR Code** will appear directly in your terminal.
* Open the **BarScan** mobile app on your phone, go to **Devices > Pair via QR**, and scan the QR code.
* Click into any document (Notepad, Excel, web form, POS software) and scan!

---

## Options & Flags

| Flag | Description | Default |
|---|---|---|
| `--port <num>` | Specify the listening port | `8765` |
| `--suffix enter\|tab\|none` | Keystroke sent after each scan | `enter` |
| `--mode type\|clipboard` | Keystroke simulation or clipboard paste (faster for 2D/QR codes) | `type` |
| `--qr-image` | Opens the QR code in your default image viewer | `false` |
| `--reset-token` | Generate a new security token | `false` |
| `--dry-run` | Test mode: prints received scans without typing | `false` |

Settings are automatically saved in `config.json`.

---

## Building a Standalone `.exe`

To share this receiver with others who don't have Python installed:
1. Double-click `build_exe.bat`.
2. PyInstaller will package everything into a single file at:
   ```
   dist\BarScanReceiver.exe
   ```
3. Distribute `BarScanReceiver.exe` to other Windows users.
