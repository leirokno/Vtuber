"""
RSS Feed Monitor Module - Patched
- Supports flat list or dict-with-metadata feed config
- Category tagging on every story
- Priority-weighted feed ordering (1=highest)
- Per-feed fetch timeout (8s) so slow feeds don't block
- GUID persistence to disk survives restarts
- 48h age gate, memory ring dedup
"""

import feedparser
import hashlib
import json
import logging
import os
import time
from datetime import datetime
from typing import Dict, List, Optional, Union
from urllib.parse import urlparse, parse_qsl, urlencode, urlunparse
from concurrent.futures import ThreadPoolExecutor, as_completed, TimeoutError

from memory_ring import is_duplicate, mark_seen

_TRACKING_KEYS = {
    "utm_source","utm_medium","utm_campaign","utm_term","utm_content",
    "utm_id","gclid","fbclid","mc_cid","mc_eid","ref","ref_src"
}

GUID_PERSIST_PATH = os.path.join(os.path.dirname(__file__), "tmp", "seen_guids.json")
FETCH_TIMEOUT     = 8      # seconds per feed
MAX_AGE_HOURS     = 48
MAX_ENTRIES_PER_FEED = 10


def canonicalize_url(url: str) -> str:
    if not url:
        return ""
    u = url.strip()
    try:
        p = urlparse(u)
        scheme = (p.scheme or "https").lower()
        netloc = (p.netloc or "").lower()
        path   = p.path or ""
        q      = [(k, v) for (k, v) in parse_qsl(p.query, keep_blank_values=True)
                  if k.lower() not in _TRACKING_KEYS]
        query  = urlencode(q, doseq=True)
        return urlunparse((scheme, netloc, path, "", query, ""))
    except Exception:
        return u


def compute_guid(entry: dict) -> str:
    guid = (entry.get("guid") or entry.get("id") or "").strip()
    if guid:
        return guid
    link = canonicalize_url((entry.get("link") or "").strip())
    if link:
        return link
    title     = (entry.get("title") or "").strip()
    published = (entry.get("published") or entry.get("updated") or "").strip()
    blob      = (title + "|" + published).encode("utf-8", errors="ignore")
    return "hash:" + hashlib.sha1(blob).hexdigest()


def _load_persisted_guids() -> set:
    try:
        os.makedirs(os.path.dirname(GUID_PERSIST_PATH), exist_ok=True)
        if os.path.exists(GUID_PERSIST_PATH):
            with open(GUID_PERSIST_PATH, "r") as f:
                data = json.load(f)
                return set(data.get("guids", []))
    except Exception:
        pass
    return set()


def _save_persisted_guids(guids: set) -> None:
    try:
        os.makedirs(os.path.dirname(GUID_PERSIST_PATH), exist_ok=True)
        # keep last 5000 to avoid unbounded growth
        trimmed = list(guids)[-5000:]
        with open(GUID_PERSIST_PATH, "w") as f:
            json.dump({"guids": trimmed, "saved_at": time.time()}, f)
    except Exception:
        pass


def _normalize_feed_list(raw) -> List[Dict]:
    """
    Accept either:
      - flat list of URL strings
      - list of {url, category, priority} dicts
      - dict with 'feeds' key
    Returns list of {url, category, priority} dicts sorted by priority asc.
    """
    if isinstance(raw, dict):
        feeds = raw.get("feeds", [])
    elif isinstance(raw, list):
        feeds = raw
    else:
        return []

    normalized = []
    for item in feeds:
        if isinstance(item, str):
            normalized.append({"url": item, "category": "general", "priority": 3})
        elif isinstance(item, dict) and item.get("url"):
            normalized.append({
                "url":      item["url"],
                "category": item.get("category", "general"),
                "priority": int(item.get("priority", 3)),
            })

    normalized.sort(key=lambda x: x["priority"])
    return normalized


def _fetch_feed(feed_meta: Dict) -> List[tuple]:
    """Fetch one feed, return list of (timestamp, entry, category, priority)."""
    url      = feed_meta["url"]
    category = feed_meta["category"]
    priority = feed_meta["priority"]
    logger   = logging.getLogger(__name__)
    results  = []
    try:
        feed = feedparser.parse(url, request_headers={"User-Agent": "AINN/1.0"})
        for entry in feed.entries[:MAX_ENTRIES_PER_FEED]:
            ts = _entry_timestamp(entry)
            results.append((ts, entry, category, priority))
    except Exception as e:
        logger.warning(f"Feed fetch error [{url}]: {e}")
    return results


def _entry_timestamp(entry) -> float:
    if entry.get("published_parsed"):
        try:
            return time.mktime(entry.published_parsed)
        except Exception:
            pass
    if entry.get("updated_parsed"):
        try:
            return time.mktime(entry.updated_parsed)
        except Exception:
            pass
    return time.time()


class RSSMonitor:
    def __init__(self, feed_urls, polling_interval: int = 90,
                 debounce_timeout: int = 10):
        self.feeds            = _normalize_feed_list(feed_urls)
        self.polling_interval = polling_interval
        self.debounce_timeout = debounce_timeout
        self.logger           = logging.getLogger(__name__)

        # in-memory + disk-backed GUID set
        self.seen_guids: set = _load_persisted_guids()

        self.last_story_guid:         Optional[str]   = None
        self.last_update_time:        Optional[datetime] = None
        self.current_story:           Optional[Dict]  = None
        self.pending_story:           Optional[Dict]  = None
        self.last_accepted_timestamp: Optional[float] = None

        self.logger.info(
            f"RSSMonitor ready — {len(self.feeds)} feeds, "
            f"{len(self.seen_guids)} persisted GUIDs loaded"
        )

    # ------------------------------------------------------------------
    def poll_feed(self, force: bool = False) -> Optional[Dict]:
        if not self.feeds:
            self.logger.warning("No RSS feeds configured")
            return None

        now_ts  = time.time()
        max_age = MAX_AGE_HOURS * 3600
        all_entries: List[tuple] = []

        # fetch all feeds in parallel with per-feed timeout
        with ThreadPoolExecutor(max_workers=min(len(self.feeds), 12)) as ex:
            futures = {ex.submit(_fetch_feed, f): f for f in self.feeds}
            for fut in as_completed(futures, timeout=FETCH_TIMEOUT + 5):
                try:
                    all_entries.extend(fut.result(timeout=FETCH_TIMEOUT))
                except (TimeoutError, Exception) as e:
                    self.logger.warning(f"Feed timeout/error: {e}")

        if not all_entries:
            return None

        # sort: priority asc (1 first), then recency desc within same priority
        all_entries.sort(key=lambda x: (x[3], -x[0]))

        for ts, entry, category, priority in all_entries:
            # age gate
            if now_ts - ts > max_age:
                continue

            entry_guid  = compute_guid(entry)
            entry_title = entry.get("title", "")

            # in-memory check
            if entry_guid in self.seen_guids:
                continue

            # memory ring persistent dedup
            dup, reason = is_duplicate(entry_guid, entry_title)
            if dup:
                self.logger.debug(f"MemRing skip [{category}]: '{entry_title[:60]}' ({reason})")
                self.seen_guids.add(entry_guid)
                continue

            # new story found
            story = self._parse_entry(entry, category=category, priority=priority)
            self.logger.info(f"[{category.upper()}] New story: {story['title'][:80]}")
            return story

        return None

    # ------------------------------------------------------------------
    def check_for_update(self, force: bool = False) -> Optional[Dict]:
        new_story = self.poll_feed(force=force)
        if new_story is None:
            return None

        now = datetime.now()
        if self.last_update_time and not force:
            elapsed = (now - self.last_update_time).total_seconds()
            if elapsed < self.debounce_timeout:
                self.logger.info(f"Debounce: {elapsed:.1f}s < {self.debounce_timeout}s")
                self.pending_story = new_story
                return None

        self._accept_story(new_story, now)
        return new_story

    def _accept_story(self, story: Dict, now: datetime) -> None:
        self.last_story_guid          = story["guid"]
        self.seen_guids.add(story["guid"])
        _save_persisted_guids(self.seen_guids)
        mark_seen(story["guid"], story.get("title", ""))
        self.last_update_time         = now
        self.current_story            = story
        self.pending_story            = None
        self.last_accepted_timestamp  = story.get("timestamp")

    def has_pending_story(self) -> bool:
        return self.pending_story is not None

    def get_pending_story(self) -> Optional[Dict]:
        if not self.pending_story:
            return None
        now = datetime.now()
        if self.last_update_time:
            if (now - self.last_update_time).total_seconds() >= self.debounce_timeout:
                story = self.pending_story
                self._accept_story(story, now)
                return story
        return None

    # ------------------------------------------------------------------
    def _parse_entry(self, entry, category: str = "general",
                     priority: int = 3) -> Dict:
        return {
            "guid":      compute_guid(entry),
            "title":     entry.get("title", "Untitled"),
            "summary":   entry.get("summary", ""),
            "link":      entry.get("link", ""),
            "published": entry.get("published", ""),
            "source":    entry.get("source", {}).get("title", "Unknown"),
            "category":  category,
            "priority":  priority,
            "timestamp": _entry_timestamp(entry),
        }

    # legacy compat shim
    def _normalize_urls(self, feed_urls):
        return [f["url"] for f in _normalize_feed_list(feed_urls)]
