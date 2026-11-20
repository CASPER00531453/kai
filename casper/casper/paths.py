"""Casper'ın verisi nerede durur: Windows'ta %APPDATA%\\Casper, başka yerde ~/.casper.

Sohbet verisi asla repoya girmez; hepsi bu klasörde.
"""

from __future__ import annotations

import os

PACKAGE_DIR = os.path.dirname(os.path.abspath(__file__))
UI_DIR = os.path.join(PACKAGE_DIR, "ui")
KNOWLEDGE_DIR = os.path.join(PACKAGE_DIR, "knowledge")


def data_dir() -> str:
    override = os.environ.get("CASPER_DATA_DIR")
    if override:
        root = override
    elif os.name == "nt":
        root = os.path.join(os.environ.get("APPDATA") or os.path.expanduser("~"), "Casper")
    else:
        root = os.path.join(os.path.expanduser("~"), ".casper")
    os.makedirs(root, exist_ok=True)
    return root


def db_path() -> str:
    return os.path.join(data_dir(), "casper.db")


def user_knowledge_dir() -> str:
    """Kullanıcının kendi eklediği bilgi notları (.md). Casper bunları da okur."""
    path = os.path.join(data_dir(), "bilgi")
    os.makedirs(path, exist_ok=True)
    return path
