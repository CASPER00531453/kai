"""Every word the user can read says Kai: no "Coucou", "Mochi" or "Louis" in the app's texts.

Only string literals in the Kotlin code and the string resources are changed. Internal
names (preference files, thread names, the relay's protocol constants) are left as they
are: nobody reads them, and renaming them would lose what a phone has stored.
"""

import glob
import os
import re

ROOT = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "app", "src", "main")
LITERAL = re.compile(r'"((?:[^"\\\n]|\\.)*)"')
WORDS = [
    ("Coucou for Android", "Kai"),
    ("Coucou link relay", "Kai link relay"),
    ("a Coucou relay", "a Kai relay"),
    ("Coucou", "Kai"),
    ("Mochi's", "Kai's"),
    ("Mochi", "Kai"),
]


def fix(text: str) -> str:
    for old, new in WORDS:
        text = text.replace(old, new)
    return text


changed = 0
for path in glob.glob(os.path.join(ROOT, "kotlin", "**", "*.kt"), recursive=True):
    src = open(path, encoding="utf-8").read()
    out = []
    for line in src.split("\n"):
        stripped = line.lstrip()
        # Comments stay as they are: only what is shown changes.
        if stripped.startswith("//") or stripped.startswith("*") or stripped.startswith("/*"):
            out.append(line)
            continue
        out.append(LITERAL.sub(lambda m: '"' + fix(m.group(1)) + '"', line))
    new = "\n".join(out)
    if new != src:
        open(path, "w", encoding="utf-8", newline="").write(new)
        changed += 1

for path in glob.glob(os.path.join(ROOT, "res", "values*", "strings.xml")):
    src = open(path, encoding="utf-8").read()
    new = re.sub(r"(<string[^>]*>)(.*?)(</string>)", lambda m: m.group(1) + fix(m.group(2)) + m.group(3), src, flags=re.S)
    if new != src:
        open(path, "w", encoding="utf-8", newline="").write(new)
        changed += 1
print(f"ok, {changed} files")
