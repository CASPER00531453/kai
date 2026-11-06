"""Kai's own strings (remote view, Home, updates), in English and Turkish; the other languages fall back to English."""

import os
import re

RES = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "app", "src", "main", "res")

EN = {
    "view_screen_title": "Computer's screen",
    "view_camera_title": "Computer's camera",
    "view_screen_button": "See the screen",
    "view_camera_button": "See the camera",
    "view_stop": "Stop",
    "view_back": "Home",
    "view_connecting": "Starting…",
    "view_live": "Live · %1$d fps",
    "view_stopped": "Stopped.",
    "view_no_camera": "No camera found on the computer.",
    "view_link_lost": "The link to the computer was lost.",
    "view_waiting": "Waiting for the first picture…",
    "view_privacy": "While you look, Kai on the computer holds a camera or a magnifying glass to its eye, so whoever is there sees it.",
    "remote_title": "Remote",
    "remote_body": "Look at the computer's screen or camera, live.",
    "remote_offline": "The computer is not connected right now.",
    "remote_turn_on": "On the computer, turn on \\\"See the screen and the camera from the phone\\\" in the Kai window › Phone.",
    "update_title": "Kai %1$s is out",
    "update_body": "A newer Kai for Android is on GitHub. Download it and open the file to update.",
    "update_button": "Download the update",
    "idle_title": "Kai is ready",
    "idle_line_approvals": "When Claude Code asks for a permission, you allow or deny it here.",
    "idle_line_questions": "Claude's questions come here too.",
    "idle_line_view": "Look at the computer's screen or camera from anywhere.",
    "idle_line_widgets": "Hold your home screen and add a Kai widget.",
}
TR = {
    "view_screen_title": "Bilgisayarın ekranı",
    "view_camera_title": "Bilgisayarın kamerası",
    "view_screen_button": "Ekranı gör",
    "view_camera_button": "Kamerayı gör",
    "view_stop": "Durdur",
    "view_back": "Ana sayfa",
    "view_connecting": "Başlıyor…",
    "view_live": "Canlı · %1$d kare/sn",
    "view_stopped": "Durdu.",
    "view_no_camera": "Bilgisayarda kamera bulunamadı.",
    "view_link_lost": "Bilgisayarla bağlantı koptu.",
    "view_waiting": "İlk görüntü bekleniyor…",
    "view_privacy": "Sen bakarken bilgisayardaki Kai gözüne kamera ya da mercek tutar; başındaki kişi bunu görür.",
    "remote_title": "Uzaktan",
    "remote_body": "Bilgisayarın ekranına ya da kamerasına canlı bak.",
    "remote_offline": "Bilgisayar şu an bağlı değil.",
    "remote_turn_on": "Bilgisayarda Kai penceresi › Telefon bölümünde \\\"Telefondan ekranı ve kamerayı gör\\\"ü aç.",
    "update_title": "Kai %1$s çıktı",
    "update_body": "Android için Kai'nin yeni sürümü GitHub'da. İndir ve dosyayı açıp güncelle.",
    "update_button": "Güncellemeyi indir",
    "idle_title": "Kai hazır",
    "idle_line_approvals": "Claude Code izin isteyince buradan izin ver ya da reddet.",
    "idle_line_questions": "Claude'un soruları da buraya gelir.",
    "idle_line_view": "Bilgisayarın ekranına ya da kamerasına her yerden bak.",
    "idle_line_widgets": "Ana ekrana basılı tut ve bir Kai widget'ı ekle.",
}


def escape(text: str) -> str:
    return text.replace("&", "&amp;").replace("<", "&lt;").replace("'", "\\'")


for folder, lines in (("values", EN), ("values-tr", TR)):
    path = os.path.join(RES, folder, "strings.xml")
    text = open(path, encoding="utf-8").read()
    for key, value in lines.items():
        row = f'    <string name="{key}">{escape(value)}</string>'
        if f'name="{key}"' in text:
            text = re.sub(rf'    <string name="{key}">.*?</string>', lambda m: row, text, flags=re.S)
        else:
            text = text.replace("</resources>", row + "\n</resources>")
    open(path, "w", encoding="utf-8", newline="").write(text)
print("ok")
