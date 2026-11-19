# Casper Patrick Jane — Plan

Bilgisayardaki ve telefondaki sohbetleri okuyan, kişileri hafızasında tutan,
gün sonunda konuştuğun insanlar hakkında yorum yapan ve dertleşebildiğin bir
asistan.

**Hedef platformlar:** Windows + Android
**Uygulamalar:** WhatsApp, Instagram, Discord
**Diller:** Python (bilgisayar tarafı, beyin), Kotlin (Android tarafı)

---

## 0. Temel ilke

Casper sadece **senin ekranına gelenleri** görür. Arkandan konuşulanları göremez.
Onun işi şu:

- ölçülebilir sinyalleri toplamak (kim ilk yazıyor, cevap süreleri, mesaj
  uzunluğu, sıcaklık, kim kimden ne istiyor),
- bunları kanıtıyla birlikte söylemek,
- belirsizliği açıkça söylemek ("bu tek mesajdan bir şey çıkmaz"),
- senin kendi düşünce tuzaklarını da yakalamak (aşağıda, Bölüm 5).

Kuruntuyu büyüten bir paranoya makinesi değil, dürüst bir gözlemci.

---

## 1. Veri kaynakları

### 1a. Geçmiş sohbetleri içe aktarma (ilk iş bu, en zengin veri)

| Uygulama | Nasıl alınır | Biçim | Not |
|---|---|---|---|
| WhatsApp | Sohbet → ⋮ → Diğer → Sohbeti dışa aktar → **Medya olmadan** | `.txt` | Tarih biçimi telefon diline göre değişir (`19.11.2026 14:32 - Ahmet: ...`). İçe aktarıcı birkaç biçimi tanımalı. Her kişi için ayrı dosya. |
| Instagram | Hesaplar Merkezi → Bilgilerini indir → Mesajlar → **JSON** | `messages/inbox/<kişi>/message_1.json` | Türkçe karakterler bozuk gelir (latin-1 olarak kodlanmış UTF-8). `text.encode("latin-1").decode("utf-8")` ile düzelir. |
| Discord | Ayarlar → Gizlilik → Verilerimi iste | `messages/c<id>/messages.json` | **Sadece senin gönderdiğin mesajlar** gelir, karşı tarafınki gelmez. Karşı taraf için ekran yakalama kullanılacak. (DiscordChatExporter iki tarafı da alır ama kullanıcı token'ı ister, Discord kurallarına aykırıdır ve hesabı riske atar. Önerilmez.) |

Hepsi tek ortak biçime çevrilir:

```
Message(platform, sohbet_id, kişi, gönderen_ben_mi, zaman, metin, kaynak)
```

### 1b. Canlı veri — Windows

- **Ekran görüntüsü:** Kai'deki `screen.py` (`PIL.ImageGrab`) yöntemi.
  Sadece WhatsApp / Instagram / Discord penceresi öndeyken ve ekran değiştiyse
  alınır (görüntü farkı ile tekrarlar elenir).
- **OCR:** Windows'un kendi OCR'ı (`Windows.Media.Ocr`, Türkçe dil paketiyle).
  Ücretsiz, yerel, hızlı. Kai zaten `winrt` kullanıyor.
- **Neden UI Automation değil:** WhatsApp ve Discord Chromium tabanlı.
  Ekran okuyucu çalışmıyorsa erişilebilirlik ağacını kapalı tutuyorlar
  (Kai'deki `desktop_chat.py` notunda da bu tespit var). OCR daha güvenilir.
- **Sohbet çözümleme:** OCR metninden kimin yazdığını, sohbetin kiminle
  olduğunu (pencere başlığı / üst başlık) ve mesajları çıkar. Zor kısım burası.
  Gerekirse belirsiz kareler ucuz bir görsel modele gönderilir.
- **Kara liste:** Banka, şifre yöneticisi, gizli sekme, belirli kişiler
  asla kaydedilmez.

### 1c. Canlı veri — Android

Kai'nin Android uygulaması (`android/`) temel alınabilir ya da ayrı küçük bir uygulama yazılır:

- **NotificationListenerService:** Gelen her WhatsApp / Instagram / Discord
  bildirimi gönderen ve metinle birlikte düz yazı olarak gelir. En kolay ve en
  temiz kaynak. Sadece gelen mesajları görür.
- **AccessibilityService:** Açık sohbet ekranındaki yazıyı okur, senin
  yazdıklarını da yakalar. Güçlü ama hassas. Kendin kurarsan (sideload) sorun
  yok, Play Store'a koymak zor.
- Telefon topladıklarını şifreli bağlantıyla bilgisayara gönderir. Kai'nin
  `phone_link.py` / `relay_link.py` TLS eşleştirmesi aynen kullanılabilir.

---

## 2. Hafıza

Hepsi bilgisayarda, `%APPDATA%\Casper` altında, şifreli.

1. **`messages.db` (SQLite):** Bütün ham mesajlar.
2. **Kişi kartları (`people/<kişi>.md`):** Kim, nereden tanışıyorsunuz,
   konuşulan konular, önemli olaylar (sınavı vardı, ayrıldı, küstünüz…),
   ilişkinin seyri, Casper'ın notları. Her gece güncellenir.
3. **Metrikler (`metrics` tablosu):** Kişi başına günlük olarak:
   - kim ilk yazdı,
   - ortalama cevap süresi (ikiniz için ayrı ayrı),
   - mesaj sayısı ve uzunluk dengesi,
   - soru sorma oranı (ilgi göstergesi),
   - ton / sıcaklık puanı.
4. **Vektör hafıza:** "Geçen ay Ahmet ne demişti?" sorusu için mesajlar ve
   özetler gömülür (embedding). SQLite + `sqlite-vec` yeterli.
5. **`about_me.md`:** Casper'ın seni tanıdığı uzun dönem dosyası. Her sohbette ona verilir.

---

## 3. "Eğitim": bilgi tabanı

Claude gibi bir modeli kendimiz yeniden eğitmiyoruz (fine-tune). Gerek de yok.
Bunun yerine Casper'a bir **bilgi kütüphanesi** veriyoruz. Konuşurken ve
analiz yaparken ilgili notları oradan çekiyor (RAG).

`knowledge/` klasörü, her kavram bir `.md` notu:

```
## Kavram adı
Ne söyler:        ...
Mesajlarda nasıl görünür:  ...
Ne kadar güvenilir:  (araştırmayla desteklenmiş / tartışmalı / mit)
Kaynak:           ...
```

Notlar internetteki kaynaklardan **kendi cümlelerimizle özetlenir**. Kitapları
olduğu gibi kopyalamıyoruz (telif). Ayrıca her nota güvenilirlik etiketi koyuyoruz,
çünkü "mentalist" dünyasının yarısı gösteri numarası.

### Konu listesi

**A. Yazışmadan ilişki okuma (araştırmayla destekli, ana malzeme)**
- Karşılıklılık: kim emek veriyor, denge
- Gottman: "bağlantı teklifleri" (bids) ve onlara dönme/dönmeme, dört atlı
  (eleştiri, aşağılama, savunma, duvar örme)
- Kendini açma ve Sosyal Nüfuz Kuramı: yakınlık açılmayla artar
- Dil stili uyumu (Linguistic Style Matching): yakın insanlar birbirine benzer yazar
- Pennebaker: zamir kullanımı, "biz" ve "ben" dili
- Cevap gecikmesi: neyi gösterir, neyi göstermez
- Bağlanma stilleri (kaygılı / kaçıngan / güvenli): hem karşı taraf hem sen için
- Dunbar'ın arkadaşlık katmanları: herkes aynı yakınlıkta olamaz, bu normal
- Nezaket kuramı, pasif agresif dil kalıpları
- Manipülasyon belirtileri: suçluluk yükleme, gaslighting, sadece işi düşünce yazma

**B. Senin zihnin (çok önemli)**
- **Liking gap:** İnsanlar başkalarının kendilerini ne kadar sevdiğini
  sistematik olarak *küçümser*. Araştırmayla gösterilmiş.
- Spotlight etkisi: Başkaları seni sandığın kadar izlemiyor.
- Bilişsel çarpıtmalar (BDT): zihin okuma, felaketleştirme, kişiselleştirme
- Olumsuzluk yanlılığı, onay yanlılığı

**C. Mentalist / gözlem (Patrick Jane tarzı, temkinli kullanılır)**
- Cold reading ve Barnum etkisi: Casper bunu *yapmamalı*. Genel geçer
  laflarla "her şeyi biliyormuş" gibi davranmasın. Bilmek için öğreniyor.
- Sherlock tarzı çıkarım: küçük ayrıntıdan sonuç, ama kanıt zinciriyle
- Beden dili ve mikro ifadeler: yazışmada işe yaramaz, büyük kısmı abartılı.
  Sadece "mit" etiketiyle bilinsin.
- NLP (Neuro-Linguistic Programming): bilimsel dayanağı yok, mit olarak etiketlenir.

---

## 4. Beyin

- **Model:** Claude API (Türkçesi ve ince yorumu iyi). Ucuz işler için küçük
  model, gece analizi ve dertleşme için büyük model.
- **Maliyet kuralı:** Görsel modele resim göndermek yerine önce yerelde OCR
  yapılır. Modele sadece metin gider.
- **Gece analizi:** Günün mesajları kişi kişi gruplanır. Her kişi için o
  kişinin kartı, son metrikler ve ilgili bilgi notları ile birlikte modele
  verilir. Çıktılar şunlar:
  - kişi başına kısa yorum + kanıt (alıntılı mesaj),
  - değişen bir şey varsa uyarı ("X bu hafta daha kısa yazıyor; ama 3 gün önce
    sınavı olduğunu söylemişti"),
  - güncellenmiş kişi kartı.
- **Haftalık rapor:** Trend grafikleri (kim yaklaşıyor, kim uzaklaşıyor) ve
  "emeğin karşılıklı mı" tablosu.

### Casper'ın kişiliği (sistem talimatı özü)

- Patrick Jane gibi dikkatli, esprili, gözlemci; ama dürüst.
- Her yorumda kanıt göster. Kanıt yoksa "bilmiyorum" de.
- Tek mesajdan sonuç çıkarma. Eğilime bak.
- Hem olumsuzu hem olumluyu söyle (insanlar olumluyu görmeyi unutuyor).
- Kullanıcı kendini kötü bir döngüye sokuyorsa bunu nazikçe söyle.

---

## 5. Arayüz

- **Telegram botu:** Telefondan da bilgisayardan da dertleşme. Gün sonu
  raporu oraya gelir.
- Komut örnekleri: `/bugun`, `/kisi Ahmet`, `/hafta`, `/unut Ahmet`, `/dur` (kaydı duraklat).
- İleride Kai'nin ses altyapısıyla sesli konuşma, Kai adasında küçük bir Casper göstergesi.

---

## 6. Güvenlik ve gizlilik

- Veritabanı şifreli (Windows DPAPI. Kai zaten sırlarını böyle saklıyor).
- **Gerçek sohbet verisi asla git'e girmez.** `data/`, `exports/`, `*.db`
  dosyaları `.gitignore`'a eklenir.
- API anahtarları `.env` / DPAPI'de durur.
- Arkadaşlarının mesajları buluttaki modele gidiyor. Bunu bilerek kullan,
  raporları kimseyle paylaşma.
- Tek tuşla "her şeyi sil".

---

## 7. Aşamalar

| # | Aşama | Çıktı |
|---|---|---|
| 1 | **İçe aktarıcılar** (WhatsApp `.txt`, Instagram JSON, Discord JSON) → `messages.db` | Geçmiş tek yerde |
| 2 | **Metrikler** + ilk kişi kartları (geçmişten) | "Kim nasıl" ilk tablo |
| 3 | **Bilgi tabanı** `knowledge/` (A, B, C) + Casper'ın kişiliği | Casper'ın "eğitimi" |
| 4 | **Telegram botu** + hafıza ile dertleşme | Konuşabilirsin |
| 5 | **Gece analizi** + günlük rapor | Her gece yorum |
| 6 | **Windows canlı yakalama** (ekran + OCR + sohbet çözümleme) | Bilgisayardan otomatik veri |
| 7 | **Android** (bildirim dinleyici → sonra erişilebilirlik) | Telefondan otomatik veri |
| 8 | Haftalık trendler, ses, Kai entegrasyonu | Cila |

İçe aktarmayla başlamak bilinçli bir seçim: canlı yakalama olmadan bile
yıllarca birikmiş sohbetin var. 1–5. aşamalar bittiğinde Casper işe yarar
hâle gelir.

---

## 8. Klasör yapısı (taslak)

```
casper/
  PLAN.md
  casper/
    importers/      whatsapp.py, instagram.py, discord.py
    capture/        windows_screen.py, ocr.py, chat_parser.py
    memory/         db.py, people.py, vectors.py
    analysis/       metrics.py, nightly.py, weekly.py
    brain/          llm.py, persona.md, rag.py
    bot/            telegram_bot.py
  knowledge/        *.md  (kavram notları)
  android/          (bildirim/erişilebilirlik servisi)
  data/             (git'e GİRMEZ)
```

---

## Yarın için ilk adım

1. Birkaç arkadaşınla WhatsApp sohbetini **medya olmadan** dışa aktar.
2. Instagram veri indirmesini **şimdiden iste** (hazırlanması saatler, bazen günler sürüyor).
3. Discord veri paketini **şimdiden iste** (birkaç gün sürebilir).
4. Bir Claude API anahtarı ve bir Telegram bot token'ı (@BotFather) hazırla.
