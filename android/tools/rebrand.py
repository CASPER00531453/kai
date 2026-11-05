"""One-time move of Coucou for Android to Kai: package, scheme, names and wording.

The code is Rhytam Biswas's under the MIT License (LICENSE). Coucou's name, the
Mochi character, the icon and the sounds are Louis Raillé's and are not part of
it: they are replaced here (the icon by tools/kai_icon.py, the sounds by
tools/kai_sounds.py, Mochi's body by Kai's ghost in MochiPainter.bodyPath).
"""

import os
import re
import shutil

ROOT = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..")
OLD_PKG, NEW_PKG = "com.coucou.android", "com.caspertechnology.kai"

# Words the user reads, in every language: the desktop's menus are Kai's, not Coucou's.
WORDING = [
    ("Coucou for Android", "Kai"),
    ("Settings, Android phone", "the Kai window, Phone"),
    ("Settings &gt; Android phone", "the Kai window &gt; Phone"),
    ("Settings > Android phone", "the Kai window > Phone"),
    ("Coucou &gt; Settings &gt; Android phone", "the Kai window &gt; Phone"),
    ("Ayarlar, Android telefon", "Kai penceresi, Telefon"),
    ("Ayarlar &gt; Android telefon", "Kai penceresi &gt; Telefon"),
    ("Coucou", "Kai"),
    ("Mochi", "Kai"),
]


def move_package() -> None:
    for source in ("main", "test", "androidTest", "debug"):
        old = os.path.join(ROOT, "app", "src", source, "kotlin", *OLD_PKG.split("."))
        if not os.path.isdir(old):
            continue
        new = os.path.join(ROOT, "app", "src", source, "kotlin", *NEW_PKG.split("."))
        os.makedirs(os.path.dirname(new), exist_ok=True)
        shutil.move(old, new)
        # The empty com/coucou folder left behind.
        leftover = os.path.dirname(old)
        if os.path.isdir(leftover) and not os.listdir(leftover):
            os.rmdir(leftover)


def rewrite(path: str) -> None:
    with open(path, encoding="utf-8") as handle:
        text = handle.read()
    new = text.replace(OLD_PKG, NEW_PKG)
    if path.endswith(".kt") or path.endswith(".kts"):
        new = new.replace('scheme != "coucou"', 'scheme != "kai"').replace('scheme == "coucou"', 'scheme == "kai"')
        new = new.replace('"_coucou._tcp"', '"_kai._tcp"').replace("coucou://pair", "kai://pair")
        new = new.replace('rootProject.name = "coucou-android"', 'rootProject.name = "kai-android"')
    elif path.endswith(".xml"):
        new = new.replace('android:scheme="coucou"', 'android:scheme="kai"').replace("coucou://", "kai://")
        if os.sep + "values" in path and os.path.basename(path).startswith("strings"):
            for old, replacement in WORDING:
                new = new.replace(old, replacement)
    if new != text:
        with open(path, "w", encoding="utf-8", newline="") as handle:
            handle.write(new)


def main() -> None:
    move_package()
    for folder, _dirs, files in os.walk(ROOT):
        if os.sep + "build" in folder or os.sep + ".gradle" in folder:
            continue
        for name in files:
            if name.endswith((".kt", ".kts", ".xml", ".pro")):
                rewrite(os.path.join(folder, name))
    # Louis's own permission note is about his assets, which Kai does not use.
    for name in ("PERMISSION.md",):
        path = os.path.join(ROOT, name)
        if os.path.exists(path):
            os.remove(path)
    print("ok")


if __name__ == "__main__":
    main()
