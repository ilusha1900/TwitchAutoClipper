import collections
import itertools
import math
import re
import statistics
import threading
import time

LAUGH_WORDS = {
    "kekw", "lul", "lulw", "omegalul", "lmao", "lol", "xd", "😂", "🤣", "💀",
}
LAUGH_LETTERS = set("хаыиоуэеявпъь")
LAUGH_LATIN = re.compile(r"(?:ha|he|hi|ah|eh){2,}h?", re.IGNORECASE)
LAUGH_RUSSIAN = re.compile(r"(?:лол+|кек+[вw]?|ору+|ржу(?:у+|нимагу|немогу)?)")
REACTION_PATTERNS = [
    re.compile(p) for p in (
        r"осужда\w*", r"[fф]+", r"\++", r"-+", r"кринж\w*",
        r"баз(?:а|ы|ой|ированн\w*|ово)", r"ба[йи]т\w*", r"рофл\w*",
        r"пизд(?:ец|ецц+|ос)",
    )
]
SILENCE_DB = -60.0
_STRIP = ".,!?:;\"'()[]{}…«»"
BOT_USERS = {
    "nightbot", "streamelements", "streamlabs", "moobot", "fossabot",
    "wizebot", "sery_bot", "commanderroot", "anotherttvviewer",
}


def _tokens(text):
    for token in text.lower().split():
        token = token.strip(_STRIP)
        if token:
            yield token


def is_laugh(token):
    token = token.lower()
    if token in LAUGH_WORDS or LAUGH_LATIN.fullmatch(token) or LAUGH_RUSSIAN.fullmatch(token):
        return True
    if len(token) >= 4 and set(token) <= LAUGH_LETTERS:
        count = token.count("х")
        return count >= 2 and count / len(token) >= 0.25
    return False


def is_reaction(token):
    return any(pattern.fullmatch(token.lower()) for pattern in REACTION_PATTERNS)


class Baseline:
    def __init__(self, floor, prior=None, history=300, min_n=10, smooth=4, use_max=False):
        if floor <= 0 or history < min_n or smooth < 1:
            raise ValueError("Invalid baseline parameters")
        self.floor, self.prior, self.min_n = floor, prior, min_n
        self.use_max = use_max
        self.hist = collections.deque(maxlen=history)
        self.recent = collections.deque(maxlen=smooth)

    def update(self, value):
        self.recent.append(value)
        signal = max(self.recent) if self.use_max else statistics.mean(self.recent)
        if len(self.hist) >= self.min_n:
            median = statistics.median(self.hist)
            mad = statistics.median(abs(x - median) for x in self.hist)
        elif self.prior is not None:
            median, mad = self.prior, 0.0
        else:
            self.hist.append(value)
            return 0.0
        scale = max(mad * 1.4826, self.floor)
        self.hist.append(max(median - 4 * scale, min(value, median + 4 * scale)))
        return max(0.0, min((signal - median) / scale, 8.0))


class MomentDetector:
    """Weighted signal OR a strong individual chat signal; volume alone is insufficient."""
    def __init__(self, cooldown=40, min_gap=20, escalate=1.5, threshold=2.5,
                 weights=None, single_threshold=6.0):
        if threshold <= 0 or single_threshold <= 0 or min_gap < 0 or cooldown < min_gap:
            raise ValueError("Invalid detector thresholds")
        self.cooldown, self.min_gap = cooldown, min_gap
        self.escalate, self.threshold = escalate, threshold
        self.single_threshold = single_threshold
        self.w = dict(weights if weights is not None else {
            "plain": 0.25, "laugh": 0.30, "react": 0.25, "vol": 0.20,
        })
        if set(self.w) != {"plain", "laugh", "react", "vol"}:
            raise ValueError("weights must contain plain, laugh, react, vol")
        if any(not math.isfinite(v) or v < 0 for v in self.w.values()) or sum(self.w.values()) <= 0:
            raise ValueError("Invalid weights")
        total = sum(self.w.values())
        self.w = {key: value / total for key, value in self.w.items()}
        self.b = {
            "plain": Baseline(floor=2.0, prior=0.0),
            "laugh": Baseline(floor=1.0, prior=0.0),
            "react": Baseline(floor=1.0, prior=0.0),
            "vol": Baseline(floor=3.0, use_max=True, smooth=3),
        }
        self._lock = threading.Lock()
        self._users = {}
        self._anon = itertools.count()
        self.last_trigger = float("-inf")
        self.last = {}
        self._peak = {}
        self.chat_matcher = None

    def set_chat_matcher(self, matcher):
        # Immutable compiled matcher is swapped as one reference; chat callbacks
        # can finish with the previous snapshot without losing user counts.
        self.chat_matcher = matcher

    def on_chat(self, text, user=None):
        if user is not None:
            user = user.lower()
            if user in BOT_USERS:
                return
        tokens = list(_tokens(text))
        matcher = self.chat_matcher
        custom_match = matcher is not None and matcher.match(text)
        if not tokens and not custom_match:
            return
        category = ("laugh" if any(is_laugh(t) for t in tokens) else
                    "react" if any(is_reaction(t) for t in tokens) or custom_match else "plain")
        priority = {"plain": 0, "react": 1, "laugh": 2}
        with self._lock:
            identity = user if user is not None else ("anonymous", next(self._anon))
            previous = self._users.get(identity)
            if previous is None or priority[category] > priority[previous]:
                self._users[identity] = category

    def _swap_counts(self):
        with self._lock:
            counts = collections.Counter(self._users.values())
            self._users.clear()
        return {key: counts[key] for key in ("plain", "laugh", "react")}

    def pop_peak(self):
        peak, self._peak = self._peak, {}
        return peak

    def tick(self, volume_db, now=None):
        now = time.time() if now is None else now
        counts = self._swap_counts()
        z = {key: self.b[key].update(value) for key, value in counts.items()}
        has_audio = (volume_db is not None and math.isfinite(volume_db)
                     and volume_db > SILENCE_DB)
        if has_audio:
            z["vol"] = self.b["vol"].update(volume_db)
        else:
            # Do not retain a pre-outage peak in the short smoothing window.
            self.b["vol"].recent.clear()
            z["vol"] = 0.0
        # Preserve weighted-score semantics; the independent route prevents
        # the old impossibility of triggering on laughter alone (0.30 * 8 < 2.5).
        score = sum(self.w[key] * value for key, value in z.items())
        chat_peak = max(z[key] for key in counts if self.w[key] > 0) if any(
            self.w[key] > 0 for key in counts) else 0.0
        strength = max(score / self.threshold, chat_peak / self.single_threshold)
        eligible = (score > self.threshold and chat_peak > 0) or chat_peak >= self.single_threshold
        self.last = {
            "t": now, "score": score, "strength": strength, **z,
            **{f"n_{key}": value for key, value in counts.items()},
            "has_audio": has_audio,
            "reason": "single_chat" if chat_peak >= self.single_threshold else "combined",
        }
        if score >= self._peak.get("score", -1):
            self._peak = dict(self.last)
        since = now - self.last_trigger
        if eligible and (since >= self.cooldown or
                         (strength >= self.escalate and since >= self.min_gap)):
            self.last["trigger_mode"] = "escalation" if since < self.cooldown else "normal"
            self.last["thresholds"] = {"score": self.threshold, "chat": self.single_threshold}
            self.last["contributions"] = {key: self.w[key] * value for key, value in z.items()}
            self.last["chat_categories"] = [key for key in counts if self.w[key] > 0 and z[key] >= self.single_threshold]
            self.last["routes"] = (["combined"] if score > self.threshold and chat_peak > 0 else []) + (["single_chat"] if chat_peak >= self.single_threshold else [])
            self.last_trigger = now
            return True
        return False
