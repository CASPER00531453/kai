# Third-party notices

Kai is made by [Casper Technology](https://casper-technology.vercel.app/) and is proprietary software, all rights reserved (see [LICENSE](LICENSE)). The installer also carries the
libraries below, each under its own license. Their license texts are in their
own projects, linked by name on PyPI or npm.

## Code Kai is built on

| Project | License | Notes |
|---|---|---|
| [Coucou](https://github.com/Louis-CFM/coucou) | MIT | The island and window interface (`_coucou_ui`). Only the code: Coucou's name, the Mochi character, its icons and its sounds are not used. |
| [Coucou for Android](https://github.com/Louis-CFM/coucou/tree/main/android) by Rhytam Biswas | MIT | The Android app (`android/`). Only the code; the phone link's protocol v1 (`phone_link.py`), the relay link (`relay_link.py`) and the Cloudflare relay Worker (`server/relay`). |

## Bundled Python libraries

| Library | License |
|---|---|
| aiohttp, aiosignal, frozenlist, multidict, propcache, yarl | Apache-2.0 (aiohttp: Apache-2.0 AND MIT) |
| aiohappyeyeballs, typing_extensions | PSF-2.0 |
| altgraph, attrs, bottle, comtypes, miniaudio, pefile, proxy_tools, pycaw, pythonnet, setuptools, six, sounddevice, tabulate, winrt-* | MIT |
| certifi | MPL-2.0 |
| cffi | MIT-0 |
| clr_loader | MIT |
| click, idna, psutil, pycparser, pypdf, pywin32-ctypes, qrcode, SpeechRecognition | BSD-3-Clause |
| cryptography | Apache-2.0 or BSD-3-Clause |
| icalendar | BSD-2-Clause |
| numpy | BSD-3-Clause (with 0BSD, MIT, Zlib, CC0-1.0 parts) |
| opencv-python-headless, PyAudioWPatch, sentencepiece, sherpa-onnx, tzdata, uiautomation, websocket-client | Apache-2.0 |
| packaging, python-dateutil | Apache-2.0 / BSD dual |
| paho-mqtt | EPL-2.0 or BSD-3-Clause |
| pillow | MIT-CMU (HPND) |
| pywebview | BSD-3-Clause |
| pywin32 | PSF |
| **edge-tts, pystray, recurring-ical-events, x-wr-timezone** | **LGPL-3.0** |
| **zeroconf** | **LGPL-2.1-or-later** |
| ifaddr | MIT |
| PyInstaller (the launcher) | GPL-2.0-or-later with the PyInstaller bootloader exception, which allows distributing apps built with it under any license |

### LGPL libraries

edge-tts, pystray, recurring-ical-events and x-wr-timezone are used unmodified,
as separate Python modules, kept as their own files inside Kai's installed
`_internal` folder. Their source is available from their projects on PyPI and
GitHub. As their license requires, you may replace them with other versions of
the same libraries; Casper Technology will provide the object files needed to
do so on request.

## Interface (npm)

| Package | License |
|---|---|
| @tauri-apps/api | Apache-2.0 OR MIT |
| vite, typescript (build only, not shipped) | MIT, Apache-2.0 |

## Downloaded on demand, not in the installer

These are fetched only when you click Download in Kai's settings:

| Model | License |
|---|---|
| Turkish voice "fahrettin" (Piper, via sherpa-onnx) | Dataset CC0 ([NabuCasa voice-datasets](https://github.com/NabuCasa/voice-datasets)); fine-tuned from Piper's "lessac" voice, whose own dataset has a research-oriented license |
| Speech recognition models (Whisper, Parakeet) | MIT (Whisper), CC-BY-4.0 (Parakeet) |

## Online services

Kai talks to services you turn on yourself (Groq, Anthropic, ElevenLabs,
Microsoft Edge's text-to-speech, GitHub, Vercel, Stripe, Spotify…). Their
terms apply to that use.
