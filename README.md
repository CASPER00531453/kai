# Kai

**A Windows companion for Claude Code.** Kai lives in a small island at the top of your screen and shows what your coding agents are doing, so you can steer them without living in the terminal.

**[⬇ Download the latest Kai for Windows](https://github.com/CASPER00531453/kai/releases/latest)** · [Kai for Android](https://github.com/CASPER00531453/kai-android/releases/latest) · [Casper Technology](https://casper-technology.vercel.app/)

## What it does

- **Claude Code on the island:** see each session's steps live. Allow or deny permissions, answer Claude's questions and approve plans right on the island. Several requests wait their turn instead of being lost.
- **Task queue:** type the next task while Claude works; when the turn ends, Claude moves on to it by itself.
- **Plan usage and a daily summary:** how much of your Claude plan is used, even when the island is compact. Every evening Kai reads you the day's report.
- **Voice:** hold a key to dictate anywhere, or say "OK Kai" and ask. Other apps go quiet while Kai listens.
- **Phone remote:** pair the Android app with a QR code to answer permissions and questions, and to see the screen or the camera, on the same Wi-Fi or from anywhere through Tailscale or your own end-to-end-encrypted Cloudflare relay. While the phone looks, Kai on the island visibly holds a camera or a magnifier.
- **And more:** a notetaker for calls, an AI chat with the provider of your choice, a memory that keeps what you tell it, mascots and outfits.

## Build from source

Requirements: Windows 10/11, Python 3.12, Node.js 20+, Inno Setup 6.

```powershell
python -m venv .venv
.\.venv\Scripts\python -m pip install -r requirements.txt
cd _coucou_ui; npm install; cd ..
.\build.ps1          # -> build\Kai-Setup-<version>.exe
```

The Android app is in `android/`; build it with `android\build-apk.ps1` (Android SDK and JDK 17).

## Licence

Kai's code is free software under the **GNU General Public License v3 or later**: see [LICENSE](LICENSE) and [NOTICE](NOTICE). The name **Kai**, the Kai mascots, the icon and the sounds are reserved by Casper Technology. You may fork the code under the GPL, but a modified version must use its own name and artwork.

Kai builds on open-source work, listed with its licences in [THIRD_PARTY_NOTICES.md](THIRD_PARTY_NOTICES.md).
