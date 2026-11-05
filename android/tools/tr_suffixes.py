"""Turkish suffixes after "Kai": the words were written for "Coucou" (back vowels), Kai takes front ones."""

import os
import re

PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "app", "src", "main", "res", "values-tr", "strings.xml")
FIX = {"yu": "yi", "yı": "yi", "dan": "den", "ya": "ye", "nun": "nin", "nın": "nin", "da": "de",
       "yla": "yle", "ta": "de", "tan": "den", "u": "yi", "ı": "yi", "na": "ne", "dur": "dir", "dır": "dir"}

text = open(PATH, encoding="utf-8").read()
text = re.sub(r"Kai(\\?')([a-zçğıöşü]+)", lambda m: "Kai" + m.group(1) + FIX.get(m.group(2), m.group(2)), text)
open(PATH, "w", encoding="utf-8", newline="").write(text)
print("ok")
