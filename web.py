"""Kai on the web: "YouTube'da X'i aç", "Google'da Y'yi ara", "github.com'a git".

There is no mouse involved. YouTube's own search page is read for its results
(the list is in the page as JSON), the chosen video is opened in the default
browser, and the answer says which one it was. Google searches and plain
sites open as they are.
"""

from __future__ import annotations

import json
import re
import urllib.parse
import urllib.request
import webbrowser

UA = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/130 Safari/537.36"
WEB_WORDS = ("youtube", "google", "video", "tarayıcı", "tarayici", "browser", "site", "web sayfa", "internette ara")


def wants_web(text: str) -> bool:
    folded = text.replace("İ", "i").replace("I", "ı").lower()
    return any(w in folded for w in WEB_WORDS) or bool(re.search(r"\b[\w-]+\.(com|net|org|io|dev|app|tr)\b", folded))


def youtube_results(query: str, count: int = 5) -> list[dict]:
    """The first videos YouTube shows for `query`: id, title, channel."""
    url = "https://www.youtube.com/results?" + urllib.parse.urlencode({"search_query": query})
    req = urllib.request.Request(url, headers={"User-Agent": UA, "Accept-Language": "tr-TR,tr;q=0.9,en;q=0.8"})
    with urllib.request.urlopen(req, timeout=15) as resp:
        html = resp.read().decode("utf-8", "ignore")
    found = re.search(r"var ytInitialData = (\{.*?\});</script>", html, re.S)
    if not found:
        return []
    data = json.loads(found.group(1))
    out: list[dict] = []

    def walk(node) -> None:
        if len(out) >= count:
            return
        if isinstance(node, dict):
            video = node.get("videoRenderer")
            if video and video.get("videoId"):
                out.append({
                    "id": video["videoId"],
                    "title": "".join(r.get("text", "") for r in (video.get("title") or {}).get("runs", [])),
                    "channel": ((video.get("ownerText") or {}).get("runs") or [{}])[0].get("text", ""),
                })
                return
            for value in node.values():
                walk(value)
        elif isinstance(node, list):
            for value in node:
                walk(value)

    walk(data)
    return out


def play_youtube(query: str, pick: int = 1, turkish: bool = True) -> str:
    """Opens the pick-th video for `query` (1 is the first) and says which one it was."""
    try:
        results = youtube_results(query, max(5, pick))
    except Exception:
        webbrowser.open("https://www.youtube.com/results?" + urllib.parse.urlencode({"search_query": query}))
        return "YouTube'un sonuçlarını okuyamadım; arama sayfasını açtım." if turkish else "I couldn't read YouTube's results; the search page is open."
    if not results:
        webbrowser.open("https://www.youtube.com/results?" + urllib.parse.urlencode({"search_query": query}))
        return "Video bulamadım; arama sayfasını açtım." if turkish else "No video found; the search page is open."
    chosen = results[min(len(results), max(1, pick)) - 1]
    webbrowser.open(f"https://www.youtube.com/watch?v={chosen['id']}")
    who = f" ({chosen['channel']})" if chosen["channel"] else ""
    answer = f"Açtım: «{chosen['title']}»{who}." if turkish else f"Playing «{chosen['title']}»{who}."
    # A fan upload often comes first; say where the official one is, if it is close.
    official = next((r for r in results[:4] if r is not chosen and re.search(r"official|resmi|resmî", r["title"], re.I)), None)
    if official and not re.search(r"official|resmi|resmî", chosen["title"], re.I):
        answer += (f" Resmi olan da aramada çıkıyor: «{official['title']}» ({official['channel']})." if turkish
                   else f" The official one is in the results too: «{official['title']}» ({official['channel']}).")
    return answer


def google(query: str, turkish: bool = True) -> str:
    webbrowser.open("https://www.google.com/search?" + urllib.parse.urlencode({"q": query}))
    return f"Google'da «{query}» aramasını açtım." if turkish else f"Google search for «{query}» is open."


def open_site(url: str, turkish: bool = True) -> str:
    url = url.strip()
    if not re.match(r"^https?://", url):
        url = "https://" + url
    if not re.match(r"^https://[\w.-]+\.[a-z]{2,}(/\S*)?$", url, re.I):
        return "Bu adresi anlayamadım." if turkish else "I couldn't make out that address."
    webbrowser.open(url)
    return f"Açtım: {url}" if turkish else f"Opened {url}"


def act(decision: dict, turkish: bool = True) -> str:
    site = str(decision.get("site") or "").lower()
    query = " ".join(str(decision.get("q") or "").split())
    if site == "youtube" and query:
        try:
            pick = int(decision.get("pick") or 1)
        except (TypeError, ValueError):
            pick = 1
        return play_youtube(query, pick, turkish)
    if site == "url" and decision.get("url"):
        return open_site(str(decision["url"]), turkish)
    if query:
        return google(query, turkish)
    return "Ne açayım? Mesela «YouTube'da Tarkan aç» de." if turkish else "What should I open? Say «play Tarkan on YouTube»."
