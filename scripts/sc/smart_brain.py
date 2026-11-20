"""Hybrid smart local transcript picker and unique catchy title generator.

Used by `--brain smart` (the default for 1-click studio jobs) as a zero-API-key fallback
whenever pre-authored Antigravity agent answers are not yet present in `work/picks`.
"""

import re
import threading

_TITLE_LOCK = threading.Lock()

# (theme_keywords, hook_template, emoji, moment_type)
SCENE_THEMES = [
    (("arrest", "handcuff", "hands up", "police", "cops", "warrant", "under arrest"),
     "GETS ARRESTED", "🚨", "reaction"),
    (("prison", "jail", "cell", "inmate", "sentence", "bail"),
     "GETS LOCKED UP", "😭", "funny"),
    (("steal", "stole", "stolen", "carjack", "hotwire"),
     "STEALS A RIDE", "💀", "funny"),
    (("crash", "black screen", "lag", "disconnect", "internet", "offline", "freeze", "frozen"),
     "STREAM CRASHES", "😱", "reaction"),
    (("save", "cannot save", "won't save", "lost everything", "reset"),
     "CANNOT SAVE GAME", "🤬", "reaction"),
    (("sneak", "sneaky", "stealth", "spotted", "caught", "hide", "alarm"),
     "FAILS STEALTH", "😭", "funny"),
    (("zoom", "wrong button", "accidentally", "didn't mean", "controls"),
     "MESSES UP CONTROLS", "💀", "funny"),
    (("waffle house", "restaurant", "burger", "food", "store", "mall", "shop"),
     "FINDS INSANE SPOT", "🤯", "reveal"),
    (("gym", "bench", "workout", "lift", "weights", "muscle"),
     "HITS THE GYM", "😂", "funny"),
    (("smoke", "cigarette", "cigar", "light up"),
     "TESTS WILD ANIMATION", "😮", "reveal"),
    (("gun", "shoot", "shot", "ammo", "reload", "sniper", "rifle", "sidearm", "fight"),
     "GOES INTO CHAOS", "🔫", "skill"),
    (("eta", "drive", "driving", "speed", "racing", "drift", "highway", "boat", "plane"),
     "LOSES IT DRIVING", "🚗", "reaction"),
    (("love", "girlfriend", "boyfriend", "date", "marriage", "kiss", "cute"),
     "FALLS FOR AN NPC", "😍", "funny"),
    (("graphics", "real", "looks so good", "unreal", "detail", "water", "lighting"),
     "IS SPEECHLESS AT GRAPHICS", "🔥", "reaction"),
    (("game inside", "mini game", "arcade"),
     "FINDS SECRET GAME", "🤯", "reveal"),
    (("betray", "snitch", "backstab", "set up", "plot twist"),
     "GETS BETRAYED", "😱", "story"),
]

HYPE_WORDS = (
    "what the", "holy", "oh my god", "no way", "crazy", "bro", "chat",
    "look at", "wtf", "insane", "run", "help", "stop", "wait", "dead",
    "hell", "fuck", "shit", "damn", "bruh", "ayo", "whoa", "scream",
)

STOPWORDS = {
    "the", "and", "that", "this", "with", "from", "your", "what", "have",
    "just", "like", "yeah", "okay", "right", "know", "they", "them", "here",
    "there", "when", "then", "into", "about", "going", "gonna", "wanna",
    "don't", "can't", "didn't", "ain't", "it's", "i'm", "you're", "we're",
}


def _short_creator(creator):
    c = (creator or "Creator").strip()
    if c.lower().endswith(" live"):
        c = c[:-5].strip()
    return c[:22] or "Streamer"


def _extract_quote_hook(text):
    """Build a short punchy 2-4 word uppercase hook from spoken dialogue when no theme matches."""
    cleaned = re.sub(r"[^a-zA-Z0-9\s'?!]", " ", text)
    words = [w for w in cleaned.split() if len(w) > 2 and w.lower() not in STOPWORDS]
    if not words:
        return "LOSES IT LIVE"
    # Pick up to 3 distinctive words
    picked = []
    seen = set()
    for w in words:
        lw = w.lower()
        if lw not in seen:
            seen.add(lw)
            picked.append(w.upper())
        if len(picked) == 3:
            break
    if len(picked) == 1:
        return f"REACTS TO {picked[0]}"
    return " ".join(picked[:3])


def _build_title(creator, topic, text, used_titles):
    short_name = _short_creator(creator)
    low = text.lower()
    topic_label = topic.strip() if topic else "Stream"

    matched_theme = None
    for keys, hook, emoji, mtype in SCENE_THEMES:
        if any(k in low for k in keys):
            matched_theme = (hook, emoji, mtype)
            break

    if matched_theme:
        hook, emoji, mtype = matched_theme
        title = f"{short_name} {hook} In {topic_label} {emoji}"
    else:
        quote_hook = _extract_quote_hook(text)
        emoji = "🔥" if "!" in text else "💀"
        mtype = "reaction"
        title = f"{short_name}: \"{quote_hook}\" In {topic_label} {emoji}"

    # Guarantee uniqueness across all clips in the same stream
    with _TITLE_LOCK:
        if title in used_titles:
            quote_hook = _extract_quote_hook(text)
            alt = f"{short_name} REACTS: {quote_hook} ({topic_label}) 😱"
            if alt in used_titles:
                idx = 2
                while f"{title} #{idx}" in used_titles:
                    idx += 1
                alt = f"{title} #{idx}"
            title = alt
        used_titles.add(title)
    return title, mtype


def _build_caption(creator, topic, title_text, excerpt):
    short_name = _short_creator(creator)
    clean_excerpt = re.sub(r"\s+", " ", excerpt).strip()
    if len(clean_excerpt) > 68:
        clean_excerpt = clean_excerpt[:65].rsplit(" ", 1)[0] + "..."
    tag_topic = re.sub(r"[^a-zA-Z0-9]", "", (topic or "gaming").lower()) or "gaming"
    tag_creator = re.sub(r"[^a-zA-Z0-9]", "", short_name.lower()) or "streamer"
    caption = f"{short_name} playing {topic}: \"{clean_excerpt}\" What would you do? 👀"
    if len(caption) > 138:
        caption = f"{short_name} crazy {topic} moment! Would you survive this? 👀"
    hashtags = [f"#{tag_topic}", f"#{tag_creator}", "#gaming", "#clips", "#shorts"]
    return caption, hashtags


def auto_pick_window(prompt_text, creator, topic, lo, hi, max_picks=3, used_titles=None):
    """Parse one transcript window prompt and return up to `max_picks` scored moments."""
    used_titles = used_titles if used_titles is not None else set()
    lines = []
    for raw in prompt_text.splitlines():
        m = re.match(r"^\[(\d+(?:\.\d+)?)\]\s*(.*)$", raw.strip())
        if not m:
            continue
        t = float(m.group(1))
        rest = m.group(2)
        vol = 0
        chat = 0
        mv = re.search(r"<<VOLUME \+(\d+) dB>>", rest)
        if mv:
            vol = int(mv.group(1))
            rest = rest.replace(mv.group(0), "")
        mc = re.search(r"<<CHAT (\d+)x>>", rest)
        if mc:
            chat = int(mc.group(1))
            rest = rest.replace(mc.group(0), "")
        clean_text = rest.strip()
        if clean_text:
            lines.append((t, vol, chat, clean_text))

    if not lines:
        return []

    scored = []
    for i, (t, vol, chat, text) in enumerate(lines):
        # Context window of ~38 seconds starting slightly before peak
        win_lines = [ln for ln in lines if t - 4 <= ln[0] <= t + 38]
        joined = " ".join(ln[3] for ln in win_lines)
        if len(joined.split()) < 12:
            continue
        low = joined.lower()
        hype_hits = sum(1 for hw in HYPE_WORDS if hw in low)
        exclam = joined.count("!") + joined.count("?")
        peak_vol = max(ln[1] for ln in win_lines)
        peak_chat = max(ln[2] for ln in win_lines)

        raw_score = 42 + peak_vol * 2.2 + peak_chat * 4.5 + min(12, hype_hits * 3) + min(8, exclam * 2)
        if raw_score < 55:
            continue
        score = int(min(97, round(raw_score)))
        c_start = max(float(lo), round(t - 4.0, 1))
        c_end = min(float(hi), round(c_start + 42.0, 1))
        if c_end - c_start < 18.0:
            continue
        scored.append((score, c_start, c_end, joined, text, peak_vol, peak_chat))

    # Pick non-overlapping highest-scoring moments
    scored.sort(key=lambda x: -x[0])
    chosen = []
    for score, s, e, joined, lead_text, p_vol, p_chat in scored:
        if any(min(e, k["end"]) - max(s, k["start"]) >= 2.0 for k in chosen):
            continue
        title, mtype = _build_title(creator, topic, joined, used_titles)
        caption, hashtags = _build_caption(creator, topic, title, lead_text)
        reasons = []
        if p_vol >= 7:
            reasons.append(f"+{p_vol} dB volume spike")
        if p_chat >= 3:
            reasons.append(f"{p_chat}x chat surge")
        if not reasons:
            reasons.append("high-energy dialogue hook")
        chosen.append({
            "start": s,
            "end": e,
            "type": mtype,
            "title": title,
            "caption": caption,
            "hashtags": hashtags,
            "score": score,
            "why": "Strong clip driven by " + " and ".join(reasons) + ".",
        })
        if len(chosen) >= max_picks:
            break
    return chosen
