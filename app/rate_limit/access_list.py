from __future__ import annotations

import logging
import time
from dataclasses import dataclass, field

logger = logging.getLogger("rate_limit.access")


@dataclass
class AccessListEntry:
    identifier: str
    reason: str = ""
    expires_at: float = 0.0

    @property
    def is_expired(self) -> bool:
        return self.expires_at > 0 and time.time() > self.expires_at


class AccessListManager:
    def __init__(
        self,
        whitelist: set[str] | None = None,
        blacklist: set[str] | None = None,
    ):
        self._whitelist: dict[str, AccessListEntry] = {}
        self._blacklist: dict[str, AccessListEntry] = {}
        for w in (whitelist or set()):
            self.add_whitelist(w)
        for b in (blacklist or set()):
            self.add_blacklist(b)

    def is_whitelisted(self, identifier: str) -> bool:
        entry = self._whitelist.get(identifier)
        if entry and not entry.is_expired:
            return True
        if entry and entry.is_expired:
            del self._whitelist[identifier]
        return False

    def is_blacklisted(self, identifier: str) -> bool:
        entry = self._blacklist.get(identifier)
        if entry and not entry.is_expired:
            return True
        if entry and entry.is_expired:
            del self._blacklist[identifier]
        return False

    def add_whitelist(self, identifier: str, reason: str = "", ttl: int = 0) -> None:
        expires_at = time.time() + ttl if ttl != 0 else 0.0
        self._whitelist[identifier] = AccessListEntry(identifier=identifier, reason=reason, expires_at=expires_at)
        logger.info("Whitelisted %s (reason=%s, ttl=%s)", identifier, reason, ttl or "permanent")

    def remove_whitelist(self, identifier: str) -> bool:
        if identifier in self._whitelist:
            del self._whitelist[identifier]
            logger.info("Removed whitelist for %s", identifier)
            return True
        return False

    def add_blacklist(self, identifier: str, reason: str = "", ttl: int = 0) -> None:
        expires_at = time.time() + ttl if ttl != 0 else 0.0
        self._blacklist[identifier] = AccessListEntry(identifier=identifier, reason=reason, expires_at=expires_at)
        logger.info("Blacklisted %s (reason=%s, ttl=%s)", identifier, reason, ttl or "permanent")

    def remove_blacklist(self, identifier: str) -> bool:
        if identifier in self._blacklist:
            del self._blacklist[identifier]
            logger.info("Removed blacklist for %s", identifier)
            return True
        return False

    def cleanup(self) -> None:
        self._whitelist = {k: v for k, v in self._whitelist.items() if not v.is_expired}
        self._blacklist = {k: v for k, v in self._blacklist.items() if not v.is_expired}

    @property
    def whitelist_count(self) -> int:
        return len(self._whitelist)

    @property
    def blacklist_count(self) -> int:
        return len(self._blacklist)
