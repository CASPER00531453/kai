// Kai window › Phone: the Android app as a remote control (phone_link.py).
// Off by default; the pairing code is shown only after a click.

import { h } from "../views/dom";
import { Api, type PhoneState } from "./api";
import type { Ctx } from "./flowpages";
import { button, card, input, L, row, segmented, toast, toggle } from "./ui";

export function phonePage(ctx: Ctx): HTMLElement {
  const f = ctx.state.flow;
  const set = async (k: string, v: unknown) => { await Api.set(k, v); await ctx.refresh(); };
  const state = h("div", { class: "a-phone-state" });
  const code = h("div", { class: "a-phone-code" });
  const actions = h("div", { class: "a-inline" });
  const routeNote = h("p", { class: "a-muted small" });
  const relayUrl = input("", "wss://kai-link.….workers.dev", () => {}, { wide: true });
  const relayKey = input("", L("erişim anahtarı (43 karakter)", "access key (43 characters)"), () => {}, { wide: true, type: "password" });
  const relayBox = h("div", { class: "a-phone-relay" },
    relayUrl, relayKey,
    h("div", { class: "a-inline" }, button(L("Kaydet", "Save"), () => void saveRelay(), "primary")),
    h("p", { class: "a-muted small", text: L(
      "Aracıyı kendi Cloudflare hesabına kurmak için Kai klasöründe server\\relay\\deploy.ps1'i çalıştır; adresi ve anahtarı Kai'ye kendisi yazar. Bağlantı uçtan uca şifreli: Cloudflare içeriği göremez.",
      "To put the relay on your own Cloudflare account, run server\\relay\\deploy.ps1 in Kai's folder; it gives Kai the address and the key itself. The link is end-to-end encrypted: Cloudflare cannot see the content.") }),
  );

  async function saveRelay() {
    const s = await Api.phone("relay", relayUrl.value, relayKey.value);
    if (s.error) return toast(L("Adres wss:// ile başlamalı, anahtar 43 karakter olmalı", "The address must start with wss:// and the key must be 43 characters"));
    relayKey.value = "";
    toast(L("Aracı kaydedildi; telefonu yeniden eşleştir", "Relay saved; pair the phone again"));
    paint(s);
  }

  function paintRoute(s: PhoneState) {
    const route = f.phone_route || "lan";
    relayBox.style.display = route === "cloudflare" ? "" : "none";
    routeNote.textContent = route === "tailscale"
      ? (s.tailscale
        ? L(`Tailscale açık: bu bilgisayar ${s.tailscale}. Telefona da Tailscale'i kur ve aynı hesapla gir; evde de dışarıda da doğrudan bağlanır, en hızlısı budur.`, `Tailscale is on: this computer is ${s.tailscale}. Install Tailscale on the phone with the same account; it connects directly at home and away, the fastest way.`)
        : L("Bu bilgisayarda Tailscale bulunamadı. tailscale.com'dan bilgisayara ve telefona kur, ikisinde de aynı hesapla gir, sonra telefonu yeniden eşleştir.", "Tailscale was not found on this computer. Install it from tailscale.com on the computer and the phone, sign in with the same account on both, then pair the phone again."))
      : route === "cloudflare"
        ? (s.relaySet
          ? L(`Aracı kurulu (${s.relay === "online" ? "bağlı" : s.relay ?? "kapalı"}). Evdeyken yerel ağdan, dışarıdayken aracıdan bağlanır.`, `The relay is set up (${s.relay ?? "off"}). At home the phone uses the local network, away the relay.`)
          : L("Aracı henüz kurulu değil: aşağıya adresini ve anahtarını gir.", "The relay is not set up yet: enter its address and key below."))
        : L("Sadece aynı Wi-Fi'deyken bağlanır. Evin dışından kontrol için Tailscale ya da Cloudflare'i seç.", "Connects only on the same Wi-Fi. For control from outside home, pick Tailscale or Cloudflare.");
  }

  function paint(s: PhoneState) {
    const on = f.phone_link;
    state.replaceChildren(
      h("i", { class: `a-phone-dot ${on && s.phones ? "ok" : on ? "wait" : "off"}` }),
      h("span", { text: !on
        ? L("Kapalı. Açınca bilgisayar telefonu dinlemeye başlar.", "Off. Turn it on and the computer listens for the phone.")
        : s.phones
          ? L(`${s.phones} telefon bağlı`, `${s.phones} phone${s.phones > 1 ? "s" : ""} connected`)
          : s.paired
            ? L("Eşleşti, telefonun bağlanmasını bekliyor", "Paired, waiting for the phone to connect")
            : L("Açık, henüz eşleşen telefon yok", "On, no phone paired yet") }),
    );
    actions.replaceChildren(
      button(s.paired ? L("Yeniden eşleştir", "Pair again") : L("Telefonu eşleştir", "Pair a phone"), () => void pair(), "primary"),
      s.paired ? button(L("Eşleşmeyi kaldır", "Unpair"), () => void unpair(), "danger") : "",
    );
    actions.style.display = on ? "" : "none";
    paintRoute(s);
  }

  async function pair() {
    const s = await Api.phone("pair");
    if (!s.link) return toast(L("Eşleştirme kodu yapılamadı", "Could not make a pairing code"));
    code.replaceChildren(
      h("img", { class: "a-phone-qr", src: s.qr, alt: "QR" }),
      h("div", { class: "a-phone-steps" },
        h("p", { text: L("1. Telefonda Kai uygulamasını aç, \"Bilgisayarı eşleştir\"e bas.", "1. Open the Kai app on the phone and tap \"Pair a computer\".") }),
        h("p", { text: L("2. Bu QR kodu okut, bilgisayarın adını onayla.", "2. Scan this QR code and confirm the computer's name.") }),
        h("p", { class: "a-muted small", text: L("Kod tek bir telefon içindir; yeniden eşleştirince eski telefon düşer. Kimseyle paylaşma.", "The code is for one phone; pairing again drops the old one. Don't share it.") }),
        button(L("Bağlantıyı kopyala", "Copy the link"), () => { void navigator.clipboard.writeText(s.link ?? ""); toast(L("Kopyalandı", "Copied")); }, "ghost"),
      ),
    );
    paint(s);
  }

  async function unpair() {
    paint(await Api.phone("unpair"));
    code.replaceChildren();
    toast(L("Eşleşme kaldırıldı", "Unpaired"));
  }

  // While the page is on screen the state follows the phone coming and going.
  const poll = window.setInterval(() => {
    if (!state.isConnected) return window.clearInterval(poll);
    void Api.phone("status").then(paint);
  }, 3000);
  void Api.phone("status").then(paint);

  return h(
    "div",
    { class: "a-page" },
    card(
      null,
      row(L("Telefondan kumanda", "Remote control from the phone"), L("Claude izin isteyince ya da soru sorunca telefonuna bildirim gelir, oradan cevaplarsın. Ajanların ne yaptığını ve plan kullanımını da görürsün.", "When Claude asks for a permission or a question, your phone is notified and you answer there. You also see what the agents do and your plan usage."), toggle(f.phone_link, (on) => void set("phone_link", on))),
      state,
      actions,
      code,
    ),
    card(
      L("Evin dışından", "From outside home"),
      row(L("Bağlantı yolu", "How the phone gets here"), L("Seçimi değiştirince telefonu yeniden eşleştir.", "Pair the phone again after changing it."),
        segmented([[L("Yerel ağ", "Local network"), "lan"], ["Tailscale", "tailscale"], ["Cloudflare", "cloudflare"]], f.phone_route || "lan", (v) => void set("phone_route", v))),
      routeNote,
      relayBox,
    ),
    card(
      L("Neler gider", "What is shared"),
      row(L("Claude'un sorularını telefondan cevapla", "Answer Claude's questions on the phone"), L("Kapalıyken sorular sadece adada çıkar.", "Off: questions show on the island only."), toggle(f.phone_answers, (on) => void set("phone_answers", on))),
      row(L("Telefondan ekranı ve kamerayı gör", "See the screen and the camera from the phone"), L("Eşleşen telefon bu bilgisayarın ekranına ya da kamerasına canlı bakabilir. Bakılırken Kai adada gözüne kamera ya da mercek tutar, yani bilgisayarın başındaki her zaman görür. Telefon başlatmadan önce parmak izini sorar.", "The paired phone can look at this computer's screen or camera, live. While it looks, Kai on the island holds a camera or a magnifying glass to its eye, so whoever is at the computer always sees it. The phone asks for the fingerprint before it starts."), toggle(f.phone_view, (on) => void set("phone_view", on))),
      h("p", { class: "a-muted small", text: L(
        "Telefona sadece ajanların durumu, izin istenen komut, Claude'un soruları ve plan yüzdesi gider. Dosyaların, sohbetlerin ve anahtarların bilgisayardan çıkmaz. İzin vermek için telefon parmak izini ya da ekran kilidini sorar.",
        "The phone only gets the agents' state, the command asking for permission, Claude's questions and the plan percentage. Your files, chats and keys never leave the computer. Allowing needs the phone's fingerprint or screen lock.") }),
    ),
    card(
      L("Bağlanmazsa", "If it doesn't connect"),
      h("p", { class: "a-muted small", text: L(
        "Telefon ve bilgisayar aynı Wi-Fi'de olmalı. İlk açılışta Windows \"Kai'nin özel ağlarda iletişim kurmasına izin ver\" diye sorarsa izin ver. Misafir ağları ve bazı modemler cihazların birbirini görmesini engeller.",
        "The phone and the computer must be on the same Wi-Fi. If Windows asks to let Kai communicate on private networks, allow it. Guest networks and some routers keep devices from seeing each other.") }),
    ),
  );
}
