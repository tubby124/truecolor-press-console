# Scanner Setup — C3070 Scan-to-SMB

The C3070's touchscreen is dead, but two things still work:

1. The **physical Scan button** on top of the scanner unit.
2. The **PageScope web admin** at `http://172.16.1.149` (printer's IP).

That's enough to use the press as a scanner and have the file land directly
on the operator laptop, where this app picks it up and offers "Inspect &
print" in one click.

## Architecture (one paragraph)

The press scans → writes the file to an SMB share on the operator laptop →
this app polls `~/Documents/PressConsole/scans/` (configurable) every 5
seconds → when a file appears, it shows up under "New scan from press" on
the home screen → operator clicks "Inspect & print" → file moves into the
existing inspect pipeline → same UX as a drag-drop.

We never drive the scanner. We're a passive consumer of files dropped into
the inbox.

---

## Step 1 — Enable File Sharing on the laptop

### Mac (the most common shop setup)

1. **System Settings → General → Sharing**
2. Turn on **File Sharing**
3. Click the **(i)** next to File Sharing → **Options**
4. Tick **Share files and folders using SMB**
5. Tick the user account that should own the share (e.g. `shop-mac`) and
   enter that user's macOS password when prompted
6. Back in **File Sharing**, click **+** under "Shared Folders"
7. Add `~/Documents/PressConsole/scans/` (create the folder first if it
   doesn't exist)
8. Set **Users** for that folder → the share user (e.g. `shop-mac`) →
   **Read & Write**

Confirm the share is reachable:

```bash
# From the laptop itself:
smbutil view -A //shop-mac@localhost
# Should list `PressConsoleScans` (or whatever you named it).
```

### Windows

1. Right-click `Documents\PressConsole\scans\` → **Properties → Sharing →
   Advanced Sharing → Share this folder**
2. **Permissions** → grant the share user **Change** + **Read**
3. Close out, then **Sharing → Network File and Folder Sharing → Share** →
   pick the user
4. Note the share path shown: `\\<laptop-name>\scans` (or similar)

Make sure the **Network discovery** + **File and printer sharing** are
turned on under **Control Panel → Network and Sharing Center → Advanced
sharing settings** for the active profile.

## Step 2 — Open the firewall

The press talks to the laptop on **TCP 445** (SMB).

### Mac
- **System Settings → Network → Firewall → Options** → make sure
  `smbd` / "File Sharing" is allowed.

### Windows
- **Windows Defender Firewall → Allow an app or feature** → ensure
  **File and Printer Sharing (SMB-In)** is enabled for the **Private**
  profile (the shop's LAN profile).

## Step 3 — Wire up PageScope

Open the press's web admin in any browser on the shop network:

> http://172.16.1.149

Log in as **admin** (default password `12345678` unless your shop already
changed it — Konica's factory default).

Navigate:

> **Store Address → Address Book → New Registration → SMB**

Fill in:

| Field          | Value |
| -------------- | ----- |
| Name           | `Press Console (Mac)` |
| Index          | (any unused — the keypad shortcut on physical scan) |
| Host Address   | The laptop's LAN IP (e.g. `172.16.1.50`) |
| File Path      | The share name (e.g. `PressConsoleScans` on Mac, `scans` on Windows) |
| User ID        | The share user (e.g. `shop-mac`) |
| Password       | The share user's password |

Save.

> **Tip:** If the laptop's IP changes (DHCP), pin a static lease on the
> shop router so PageScope's address-book entry doesn't go stale.

## Step 4 — Scan a test page

1. Place a sheet face-up on the **document feeder** (or face-down on the
   glass).
2. **Press the physical Scan button** on the top right of the scanner unit
   (not the touchscreen — that's dead).
3. On the small physical display, pick **Press Console (Mac)** from the
   stored destinations.
4. Press the green **Start** button.

Within 5 seconds, the file should appear in:

```
~/Documents/PressConsole/scans/
```

…and "New scan from press" should appear on the home screen of this app.

## Step 5 — Configure a non-default inbox path (optional)

The default is `~/Documents/PressConsole/scans/`. To point somewhere else
(network share, specific subfolder), set the env var before launching:

```bash
PRESS_SCANNER_INBOX="/Volumes/ShopShare/scans" \
  python -m backend.main
```

If the path doesn't exist, the app creates it on first request.

## Troubleshooting

### Scans never show up in the app

1. **Did the file actually land?**
   ```bash
   ls -la ~/Documents/PressConsole/scans/
   ```
   If yes but the app doesn't show it: hard-refresh the browser. The app
   polls every 5s.

2. **Is the inbox writable?**
   ```bash
   touch ~/Documents/PressConsole/scans/.test && rm ~/Documents/PressConsole/scans/.test
   ```
   If this errors, fix the permissions before re-scanning.

3. **Did the press connect to SMB at all?**
   In PageScope: **Job → Communication Log**. SMB auth failures show as
   `Send error` with code `0x...`. The most common cause is a wrong
   password or a typo'd share path.

4. **Firewall**
   Try sharing the folder, scanning, and watching with `tcpdump`:
   ```bash
   sudo tcpdump -ni en0 'host 172.16.1.149 and tcp port 445'
   ```
   If you see the SYN but no ACK back, the firewall is dropping it.

### "Inspect & print" fails after import

The scan landed but normalize.py couldn't read it. Most common causes:

- TIFF compression the system imagemagick doesn't support → re-scan as PDF
- 0-byte file (press SMB error, partial write) → just dismiss and rescan

### Auto-purge

Dismissed scans go to `~/Documents/PressConsole/scans/_dismissed/` and
auto-purge after 30 days (matches `settings.purge_jobs_after_days`). Active
inbox files are never auto-deleted — they only go away when the operator
imports or dismisses them, or manually deletes them in Finder.
