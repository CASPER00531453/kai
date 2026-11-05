# Kai for Android

The remote control of Kai on your phone. It connects to Kai on your computer over the local
network (Kai window › Phone) and shows what your coding agents are doing; you allow or deny their
permission requests and answer Claude Code's questions from the phone. Allowing needs the phone's
fingerprint or screen lock.

Protocol: v1 of the Android link (`phone_link.py` on the computer is the server). Android 11 or later.

## Build

    powershell -File android\build-apk.ps1            # debug APK -> build\Kai-Android-<version>.apk
    powershell -File android\build-apk.ps1 assembleRelease

The Android tools refuse a project path with non-ASCII letters, so the script mirrors this folder
to `%LOCALAPPDATA%\KaiBuild\android` and builds there. It needs the Android SDK
(`%LOCALAPPDATA%\Android\Sdk`) and JDK 17.

## Kai's own look

- `tools/kai_icon.py` draws the launcher icon, `tools/kai_sounds.py` the sounds,
  `tools/kai_vectors.py` the widget previews and the status bar icon.
- The mascot on screen is Kai's ghost (`mochi/MochiPainter.bodyPath`).
- `tools/rebrand.py` and `tools/credits.py` did the one-time move from Coucou for Android.

## Licence

See `NOTICE.md`: Kai for Android is © Casper Technology; the Android code it is built on is
© Rhytam Biswas under the MIT License (`LICENSE`).
