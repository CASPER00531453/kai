"""The About and licence lines, in every language: Kai is Casper Technology's; the Android
code it is built on is Rhytam Biswas's under the MIT License (Coucou for Android)."""

import glob
import os
import re

RES = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "app", "src", "main", "res")

EN = {
    "about_credit": "Kai for Android, by Casper Technology. Built on Coucou for Android by Rhytam Biswas (MIT License).",
    "about_repo": "casper-technology.vercel.app",
    "licences_intro": "The name Kai, its mascots, the icon and the sounds are Casper Technology\\'s. The Android code Kai is built on is MIT-licensed. The libraries are listed with their licence.",
    "about_assets": "Kai, its mascots, the icon and the sounds are © Casper Technology. Parts of the Android code are © Rhytam Biswas (Coucou for Android), used under the MIT License.",
    "pairing_credit": "Kai for Android, by Casper Technology.",
}
TR = {
    "about_credit": "Android için Kai, Casper Technology tarafından. Rhytam Biswas\\'ın Coucou for Android kodu üzerine kuruldu (MIT Lisansı).",
    "about_repo": "casper-technology.vercel.app",
    "licences_intro": "Kai adı, maskotları, simgesi ve sesleri Casper Technology\\'ye aittir. Kai\\'nin üzerine kurulduğu Android kodu MIT lisanslıdır. Kütüphaneler lisanslarıyla birlikte listelenmiştir.",
    "about_assets": "Kai, maskotları, simgesi ve sesleri © Casper Technology. Android kodunun bazı bölümleri © Rhytam Biswas (Coucou for Android), MIT Lisansı ile kullanılmaktadır.",
    "pairing_credit": "Android için Kai, Casper Technology tarafından.",
}

for path in glob.glob(os.path.join(RES, "values*", "strings.xml")):
    lines = TR if os.path.basename(os.path.dirname(path)) == "values-tr" else EN
    text = open(path, encoding="utf-8").read()
    for key, value in lines.items():
        text = re.sub(rf'(<string name="{key}">)(.*?)(</string>)', lambda m: m.group(1) + value + m.group(3), text, flags=re.S)
    open(path, "w", encoding="utf-8", newline="").write(text)
print("ok")
