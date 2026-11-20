# Casper Patrick Jane

Sohbetlerini okuyan, konuştuğun insanları hatırlayan, ekranını izleyip yorum yapan ve dertleşebildiğin kişisel gözlemci. Windows için.

- **Dertleş:** Casper seni ve kişilerini hatırlar. Birinin adını yazınca onun geçmişine bakar.
- **Kişiler:** Kişi oluştur, kişinin **Ayarlar · Sohbet yükle** sekmesinden WhatsApp, Instagram ya da Discord sohbetini yükle. Casper ölçümleri çıkarır (kim başlatıyor, cevap süreleri, cevapsız kalanlar, küfür/atışma) ve **Casper'a analiz ettir** ile kanıtlı yorum yapar.
- **Gözcü:** 2, 3 ya da 5 saniyede bir öndeki sohbet penceresine bakar, ekrandaki yazıyı Windows OCR ile okur, ikinci ekrandaki panelde yorum yapar.
- **Gün sonu:** Her gün belirlediğin saatte o günün raporunu yazar.
- **Hafıza:** Casper'ın senin hakkında hatırladıkları; ekleyip silebilirsin.

## Kurulum (Windows)

1. [Python 3.12](https://www.python.org/downloads/) kur ("Add to PATH" işaretli).
2. Türkçe OCR için: **Ayarlar → Saat ve dil → Dil ve bölge → Türkçe**'nin yüklü olduğundan emin ol. Türkçe yoksa Windows OCR başka dille okur. Hiç yoksa gözcü ekran görüntüsünü doğrudan Claude'a gönderir, bu daha pahalıdır.
3. Bu klasörde:

```powershell
cd casper
python -m venv .venv
.\.venv\Scripts\python -m pip install -r requirements.txt
.\.venv\Scripts\python run.py
```

4. Açılınca **Ayarlar**'a [console.anthropic.com](https://console.anthropic.com)'dan aldığın Claude API anahtarını yapıştır ve **Dene**'ye bas. Anahtar bu Windows kullanıcısına şifreli saklanır (DPAPI).
5. **Ayarlar → Sen kimsin?** kısmına sohbetlerde görünen adlarını yaz (WhatsApp adın, Instagram kullanıcı adın). İçe aktarırken hangi mesajların senin olduğunu bundan tahmin eder.

## Sohbetleri yükleme

| Platform | Ne seçeceksin |
|---|---|
| WhatsApp | Sohbeti dışa aktar → Medya olmadan. Gelen `.zip`'i ya da içindeki `.txt`'yi seç. |
| Instagram | JSON paketinin `.zip`'ini seç. İçindeki bütün sohbetler listelenir, o kişiyle olanı işaretle. |
| Discord | `package.zip`'i seç. Pakette **sadece senin mesajların** var; karşı tarafınkini gözcü modu görür. |

Aynı dosyayı tekrar yüklemek sorun değil; aynı mesaj iki kez eklenmez.

## Küfür

`amk`, `aq`, `lan`, `oha`, `siktir`, `amına koyim` gibi kelimeler **gündelik** sayılır, hiçbir yorumu etkilemez. "Mal", "salak" gibi lakaplar ve gülme işaretiyle (hahaha, sjsjsj, 😂, 💀) gelen ağır kelimeler **atışma**dır; arkadaşlıkta normaldir. Sadece aileye yönelik ciddi küfür (**dikkat**), tehdit ve aşağılama (**ağır**) sorun olarak işaretlenir. Casper da tek mesaja değil, eğilime bakar: artıyor mu, tek taraflı mı?

## Casper'ı "eğitmek"

Casper'ın bilgi kütüphanesi `casper/knowledge/` içinde: karşılıklılık, Gottman, bağlanma stilleri, sevilme açığı, mentalist teknikleri ve mitler, Türk arkadaşlık kültürü. Kendi notlarını eklemek için **Ayarlar → Bilgi klasörünü aç**'a bas ve oraya `.md` dosyası koy. Casper bir sonraki konuşmada onları da okur.

## Gizlilik

- Bütün veri `%APPDATA%\Casper` klasöründe durur. Repoya hiçbir sohbet girmez.
- Mesajlar yorum için Claude API'ye gönderilir. Arkadaşlarının mesajları da buna dahil; raporları kimseyle paylaşma.
- Gözcü, başlığında `banka`, `şifre`, `password`, `incognito`, `InPrivate` gibi kelimeler geçen pencerelere bakmaz (liste Ayarlar'da). Ekran görüntüleri diske kaydedilmez.
- **Ayarlar → Her şeyi sil** bütün veriyi siler.

## Maliyet

Varsayılan model Claude Opus 5.5 (en iyi yorum). Gözcü modu sık çalıştığı için Gözcü sayfasında modeli **Haiku 5.5** yapmak maliyeti çok düşürür. Ekran görüntüsü 2-5 saniyede bir alınır ama Claude'a sadece yeni yazı biriktiğinde ve bekleme süresi (varsayılan 20 sn) dolunca gidilir.

## Testler

```powershell
.\.venv\Scripts\python -m pip install pytest
.\.venv\Scripts\python -m pytest tests
```
