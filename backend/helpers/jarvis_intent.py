import json
import os
import re

from helpers.jarvis_local import extract_path_candidate, try_local_intent
from helpers.jarvis_web import looks_like_web_search
from schemas.jarvis import JarvisIntent

_RULE_FIRST_MIN_CONF = 0.88

_RULES: list[tuple[re.Pattern[str], str, float, dict[str, str]]] = []


def _rule(pattern: str, intent: str, confidence: float = 0.92, **slot_keys: str) -> None:
    _RULES.append((re.compile(pattern, re.I), intent, confidence, slot_keys))


_rule(r"^(hi|hello|hey|good\s+(morning|afternoon|evening))(?:\s+jarvis|\s+guardian)?\b", "greet", 0.95)
_rule(r"^(thanks|thank\s+you|ok|okay|got\s+it)\b", "acknowledge", 0.9)
_rule(r"what(?:'s| is)? the time|what time is it|tell me the time|current time", "time", 0.94)
_rule(r"what(?:'s| is)? the date|what date is it|today(?:'s)? date", "date", 0.94)
_rule(r"lock(?: the)? (?:pc|computer|screen|system)|lock workstation", "lock", 0.93)
_rule(
    r"(?:please\s+)?(?:(?:turn|set)\s+)?(?:the\s+)?(?:volume|sound)\s+(?:up|higher|louder)"
    r"|(?:increase|raise)\s+(?:the\s+)?(?:volume|sound)",
    "volume_up",
    0.92,
)
_rule(
    r"(?:please\s+)?(?:(?:turn|set)\s+)?(?:the\s+)?(?:volume|sound)\s+(?:down|lower|quieter)"
    r"|(?:decrease|lower|reduce)\s+(?:the\s+)?(?:volume|sound)",
    "volume_down",
    0.92,
)
_rule(r"(?:please\s+)?(?:mute|unmute|toggle mute)", "volume_mute", 0.9)
_rule(
    r"open youtube and (?:play|search)(?:\s+for)?(?:\s+the)?\s+song\s+['\"]?(?P<query>.+?)['\"]?\s*$",
    "youtube_search",
    0.97,
    query="query",
)
_rule(
    r"open youtube and (?:play|search)(?:\s+for)?\s+['\"]?(?P<query>.+?)['\"]?\s*$",
    "youtube_search",
    0.96,
    query="query",
)
_rule(
    r"(?:play|search)(?:\s+for)?(?:\s+the)?\s+song\s+['\"]?(?P<query>.+?)['\"]?\s+on youtube\s*$",
    "youtube_search",
    0.96,
    query="query",
)
_rule(r"open (?:the )?(?P<app>[\w\s]+?)(?:\s+app)?$", "open_app", 0.9, app="app")
_rule(r"launch (?:the )?(?P<app>[\w\s]+)$", "open_app", 0.88, app="app")
_rule(r"(?:go to|open) (?P<url>https?://\S+)", "open_url", 0.95, url="url")
_rule(r"open (?:the )?(?:website|site|page) (?P<query>.+)", "open_url_search", 0.85, query="query")
_rule(r"search (?:on )?(?:the )?(?:web|internet|online|google)(?:\s+for)?\s+(?P<query>.+)", "web_search", 0.94, query="query")
_rule(r"search (?:for )?(?P<query>.+)", "web_search", 0.9, query="query")
_rule(r"(?:google|googling)\s+(?:for\s+)?(?P<query>.+)", "web_search", 0.9, query="query")
_rule(r"(?:look\s*up|lookup|find|browse)\s+(?P<query>.+)\s+(?:on\s+)?(?:the\s+)?(?:web|internet|online|google)", "web_search", 0.9, query="query")
_rule(r"(?:look\s*up|lookup|find)\s+(?P<query>.+)", "web_search", 0.86, query="query")
_rule(r"open (?:my )?(?P<folder>desktop|documents|downloads|home|pictures)", "open_folder", 0.9, folder="folder")
_rule(
    r"(?:open|launch|start)\s+(?:the\s+)?(?:(windows\s+)?terminal|wt)\b",
    "open_terminal",
    0.94,
)
_rule(
    r"(?:open|launch|start)\s+(?:the\s+)?(?P<shell>command\s+prompt|cmd)\b",
    "open_terminal",
    0.93,
    shell="shell",
)
_rule(
    r"(?:open|launch|start)\s+(?:the\s+)?(?P<shell>powershell|pwsh)\b",
    "open_terminal",
    0.93,
    shell="shell",
)
_rule(r"minimize (?:all )?windows|show desktop", "minimize_all", 0.9)
_rule(r"(?:take )?screenshot|capture screen", "screenshot", 0.9)
_rule(
    r"shut\s*down|shut\s+down\s+(?:my\s+)?(?:the\s+)?(?:pc|computer|laptop|system)|power\s+off",
    "shutdown",
    0.92,
)
_rule(r"restart\s+(?:my\s+)?(?:the\s+)?(?:pc|computer|laptop|system)|reboot", "restart", 0.92)
_rule(r"cancel|stop listening|never mind", "cancel", 0.9)
_rule(r"help|what can you do|capabilities", "help", 0.95)


def _parse_with_llm(text: str) -> JarvisIntent | None:
    use_llm = os.getenv("JARVIS_USE_LLM", "true").lower() in ("1", "true", "yes")
    if not use_llm:
        return None

    from helpers.jarvis_groq import groq_enabled, parse_intent_with_groq

    if groq_enabled():
        return parse_intent_with_groq(text)

    api_key = os.getenv("OPENAI_API_KEY", "").strip()
    if not api_key:
        return None
    try:
        from openai import OpenAI  # type: ignore

        client = OpenAI(api_key=api_key)
        prompt = (
            "Parse this voice command into JSON with keys: intent, confidence (0-1), slots (object). "
            "Intents: greet, time, date, lock, volume_up, volume_down, volume_mute, open_app, "
            "open_url, web_search, open_folder, open_path, open_terminal, minimize_all, screenshot, "
            "shutdown, restart, youtube_search, help, acknowledge, cancel, unknown. "
            "open_path: local file/folder; slots.path = full Windows path or a drive root like C: plus backslash. "
            "open_terminal: slots.shell is wt, cmd, or powershell. "
            "Never use web_search for terminal, cmd, PowerShell, C: drive, or file paths. "
            f"Command: {text}"
        )
        resp = client.chat.completions.create(
            model="gpt-4o-mini",
            messages=[{"role": "user", "content": prompt}],
            max_tokens=120,
        )
        data = json.loads(resp.choices[0].message.content or "{}")
        raw_slots = data.get("slots") or {}
        slots: dict[str, str] = {}
        if isinstance(raw_slots, dict):
            for k, v in raw_slots.items():
                if v is None:
                    continue
                slots[str(k).strip()] = str(v).strip()
        return JarvisIntent(
            intent=str(data.get("intent", "unknown")).strip() or "unknown",
            confidence=float(data.get("confidence", 0.7)),
            slots=slots,
        )
    except Exception:
        return None


def _sanitize_llm_intent(intent: JarvisIntent, clean: str) -> JarvisIntent:
    repaired = try_local_intent(clean)
    if repaired and intent.intent in ("web_search", "unknown", "open_app"):
        if intent.intent != "open_app" or repaired.intent in ("open_path", "open_terminal"):
            return repaired
    pc = extract_path_candidate(clean)
    if pc and intent.intent == "open_path" and not (intent.slots.get("path") or "").strip():
        return JarvisIntent(
            intent="open_path",
            confidence=max(intent.confidence, 0.88),
            slots={"path": pc},
        )
    return intent


def parse_jarvis_intent(text: str) -> JarvisIntent:
    clean = " ".join(text.strip().split())
    if not clean:
        return JarvisIntent(intent="unknown", confidence=0.0)

    use_llm = os.getenv("JARVIS_USE_LLM", "true").lower() in ("1", "true", "yes")
    if use_llm:
        llm = _parse_with_llm(clean)
        if llm and llm.confidence >= 0.65:
            return _sanitize_llm_intent(llm, clean)

    local = try_local_intent(clean)
    if local:
        return local

    best: JarvisIntent | None = None
    for pattern, intent, confidence, slot_map in _RULES:
        match = pattern.search(clean)
        if not match:
            continue
        slots: dict[str, str] = {}
        for slot_name, group_name in slot_map.items():
            val = match.group(group_name)
            if val:
                slots[slot_name] = val.strip()
        if best is None or confidence > best.confidence:
            best = JarvisIntent(intent=intent, confidence=confidence, slots=slots)

    if best and best.confidence >= _RULE_FIRST_MIN_CONF:
        return best

    if best:
        return best

    lower = clean.lower()
    if lower.startswith("open "):
        pc = extract_path_candidate(clean)
        if pc:
            return JarvisIntent(intent="open_path", confidence=0.84, slots={"path": pc})
        target = clean[5:].strip()
        if target.startswith("http"):
            return JarvisIntent(intent="open_url", confidence=0.75, slots={"url": target})
        if target.lower() == "youtube":
            return JarvisIntent(
                intent="open_url",
                confidence=0.9,
                slots={"url": "https://www.youtube.com"},
            )
        if "youtube" in target.lower() and re.search(r"\b(play|search|song)\b", target.lower()):
            song = re.search(
                r"(?:play|search)(?:\s+for)?(?:\s+the)?\s+song\s+['\"]?(.+?)['\"]?\s*$",
                target,
                re.I,
            )
            if song:
                return JarvisIntent(
                    intent="youtube_search",
                    confidence=0.85,
                    slots={"query": song.group(1).strip()},
                )
        if looks_like_web_search(target):
            return JarvisIntent(intent="web_search", confidence=0.85, slots={"query": target})
        return JarvisIntent(intent="open_app", confidence=0.7, slots={"app": target})

    if re.search(r"\b(search|google|look\s*up|find)\b", lower) and not lower.startswith("open "):
        query = re.sub(
            r"^(?:please\s+)?(?:can you\s+)?(?:search(?:\s+for)?|google|look\s*up|find)\s+",
            "",
            clean,
            flags=re.I,
        ).strip()
        if query:
            return JarvisIntent(intent="web_search", confidence=0.75, slots={"query": query})

    if re.search(r"\b(volume|sound)\b", lower) and re.search(
        r"\b(up|down|higher|lower|louder|quieter|increase|decrease|mute)\b", lower
    ):
        if re.search(r"\b(down|lower|quieter|decrease|reduce)\b", lower):
            return JarvisIntent(intent="volume_down", confidence=0.8)
        if re.search(r"\b(mute|unmute)\b", lower):
            return JarvisIntent(intent="volume_mute", confidence=0.8)
        if re.search(r"\b(up|higher|louder|increase|raise)\b", lower):
            return JarvisIntent(intent="volume_up", confidence=0.8)

    return JarvisIntent(intent="unknown", confidence=0.3, slots={"raw": clean})
