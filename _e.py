import media
from island import Island, enable_dpi

enable_dpi()
media.refresh()
isl = Island(lambda *a: None)
isl.media = media.current
isl.size_percent = 50
isl.rest = True

isl.mode = "media"
isl.shown = isl.target = 1.0
isl._draw().save("preview-media.png")
print("buttons", isl.buttons)

isl.mode = "listen"
isl.subtitle = ""
isl.chat = True
isl.you = "Yarın İstanbul'da yağmur yağacak mı?"
isl.kai_line = "Patron, yarın İstanbul'da parçalı bulutlu bir hava bekleniyor, akşama doğru hafif sağanak geçiş ihtimali var. Şemsiyeyi yanına almanda fayda var."
isl._draw().save("preview-chat.png")

isl.kai_line = ""
isl.typing = True
isl.tick = 5
isl._draw().save("preview-typing.png")
isl.destroy()
