# Attention 🎯

Reels/TikTok bağımlılığına karşı Android uygulaması. Dikkat dağıtan uygulamaları kilitler;
açmak için ya **odak oturumu** tamamlarsın ya da yaptığın işi **fotoğrafla kanıtlarsın** ve
Groq üzerindeki AI fotoğrafı kontrol eder.

## Nasıl çalışır
1. **Odak seç:** 📚 Ders, 💻 Kod, 🏋️ Gym veya 🎯 Özel (kendin yaz).
2. **Uygulamaları seç:** Instagram, TikTok, YouTube… Seçilenler molan yokken açılamaz.
3. **Kilidi aç:**
   - **⏱ Odak oturumu:** 15–90 dk. Süre boyunca her şey kilitli; bitince mola kazanırsın (25 dk → 8 dk, 60 dk → 20 dk).
   - **📸 Fotoğraf kanıtı:** Kamerayla anlık fotoğraf çek (galeri yok). AI (`llama-4-scout` vision) onaylarsa 15 dk mola.
     İki kanıt arasında 45 dk bekleme var, yani "çalış → kanıtla → mola" döngüsü.
4. Kilitli uygulamayı açmaya çalışınca tam ekran engel çıkar ve AI koç sana kısa bir laf sokar.

Oturum sürerken engelleme kapatılamaz ve listeden uygulama çıkarılamaz.

## Kurulum
1. GitHub → **Actions** → *Attention Android APK* → son çalıştırma → **Attention-apk** dosyasını indir
   (veya `attention-v*` etiketiyle yayınlanan **Releases** sayfasından `Attention.apk`).
2. APK'yı telefona kur (bilinmeyen kaynaklara izin ver).
3. Uygulamada **Erişilebilirliği aç** → Attention'ı etkinleştir.
   Android 13+ gri gösterirse: *Ayarlar → Uygulamalar → Attention → ⋮ → Kısıtlanmış ayarlara izin ver*.
4. [console.groq.com](https://console.groq.com) → API Keys → anahtar oluştur → uygulamada **Ayarlar**'a yapıştır → **Test et**.

API anahtarı sadece telefonda saklanır; fotoğraflar yalnızca kontrol için Groq'a gönderilir ve sonra silinir.

## Geliştirme
Kotlin + Jetpack Compose, minSdk 26. `cd attention && ./gradlew assembleRelease`
(Android SDK gerekir). Engelleme bir `AccessibilityService` ile yapılır, ekran içeriği okunmaz.
