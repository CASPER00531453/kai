"""Casper Patrick Jane'i başlat:  python run.py   (geliştirici araçlarıyla: python run.py --debug)"""

import os
import sys
import traceback


def _log_to_file() -> None:
    """Konsolsuz .exe'de hatalar kaybolmasın: %APPDATA%\\Casper\\casper.log"""
    from casper import paths

    log = open(os.path.join(paths.data_dir(), "casper.log"), "a", encoding="utf-8", buffering=1)
    sys.stdout = sys.stderr = log


if __name__ == "__main__":
    if getattr(sys, "frozen", False):
        _log_to_file()
    try:
        from casper.app import CasperApp

        CasperApp().run(debug="--debug" in sys.argv)
    except Exception:
        traceback.print_exc()
        if os.name == "nt":
            import ctypes

            ctypes.windll.user32.MessageBoxW(
                None, "Casper açılamadı. Ayrıntı: %APPDATA%\\Casper\\casper.log\n\n" + traceback.format_exc()[-800:],
                "Casper", 0x10,
            )
        raise
