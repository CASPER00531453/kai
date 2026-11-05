// Kai window › Phone: the Android app as a remote control (phone_link.py).
// Off by default; the pairing code is shown only after a click.

import { h } from "../views/dom";
import { Api, type PhoneState } from "./api";
import type { Ctx } from "./flowpages";
import { button, card, L, row, toast, toggle } from "./ui";

export function phonePage(ctx: Ctx): HTMLElement {
  const f = ctx.state.flow;
  const set = async (k: string, v: unknown) => { await Api.set(k, v); await ctx.refresh(); };
  const state = h("div", { class: "a-phone-state" });
  const code = h("div", { class: "a-phone-code" });
  const actions = h("div", { class: "a-inline" });

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
      L("Neler gider", "What is shared"),
      row(L("Claude'un sorularını telefondan cevapla", "Answer Claude's questions on the phone"), L("Kapalıyken sorular sadece adada çıkar.", "Off: questions show on the island only."), toggle(f.phone_answers, (on) => void set("phone_answers", on))),
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
