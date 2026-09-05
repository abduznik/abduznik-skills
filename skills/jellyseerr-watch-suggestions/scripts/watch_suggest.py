#!/usr/bin/env python3
"""Watch suggestions: Jellyseerr trending filtered by Sonarr/Radarr ownership
and Jellyseerr pending requests. All endpoints/credentials come from env vars.

Required env vars:
  SEERR_URL (default http://localhost:5055)
  SONARR_URL (default http://localhost:8989)
  RADARR_URL (default http://localhost:7878)
  SONARR_API_KEY, RADARR_API_KEY, SEERR_USER, SEERR_PASSWORD
"""
import http.cookiejar
import json
import os
import urllib.request


def env(name: str, default: str = "") -> str:
    v = os.environ.get(name, default)
    if not v:
        raise SystemExit(f"missing env var {name}")
    return v


SEERR_URL = env("SEERR_URL", "http://localhost:5055").rstrip("/")
SONARR_URL = env("SONARR_URL", "http://localhost:8989").rstrip("/")
RADARR_URL = env("RADARR_URL", "http://localhost:7878").rstrip("/")
SONARR_KEY = env("SONARR_API_KEY")
RADARR_KEY = env("RADARR_API_KEY")
SEERR_USER = env("SEERR_USER")
SEERR_PASS = env("SEERR_PASSWORD")


def get(url: str, headers: dict | None = None) -> dict:
    req = urllib.request.Request(url, headers=headers or {})
    with urllib.request.urlopen(req, timeout=25) as r:
        return json.loads(r.read().decode())


def seerr_session():
    """Login once, keep the cookie jar, return a path-caller."""
    cj = http.cookiejar.CookieJar()
    opener = urllib.request.build_opener(urllib.request.HTTPCookieProcessor(cj))
    login = urllib.request.Request(
        SEERR_URL + "/api/v1/auth/local",
        data=json.dumps(
            {"username": SEERR_USER, "email": "local@local", "password": SEERR_PASS}
        ).encode(),
        headers={"Content-Type": "application/json"},
    )
    opener.open(login, timeout=25).read()

    def call(path: str) -> dict:
        req = urllib.request.Request(SEERR_URL + path)
        with opener.open(req, timeout=25) as r:
            return json.loads(r.read().decode())

    return call


def main() -> None:
    owned_tv = {s["title"].lower() for s in get(SONARR_URL + "/api/v3/series", {"X-Api-Key": SONARR_KEY})}
    owned_mv = {m["title"].lower() for m in get(RADARR_URL + "/api/v3/movie", {"X-Api-Key": RADARR_KEY})}
    jse = seerr_session()

    reqd: set[str] = set()
    for f in ("requested", "processing"):
        d = jse(f"/api/v1/media?filter={f}&take=100&skip=0")
        for m in d.get("results", []):
            nm = (m.get("title") or m.get("name") or "").lower()
            if nm:
                reqd.add(nm)

    seen: set[str] = set()
    cands = []
    for media_type in ("movie", "tv"):
        for page in (1, 2, 3):
            d = jse(f"/api/v1/discover/trending?page={page}&language=en")
            for r in d.get("results", []):
                if r.get("mediaType") != media_type:
                    continue
                t = (r.get("title") or r.get("name") or "").lower().strip()
                if not t or t in seen:
                    continue
                seen.add(t)
                owned = t in (owned_mv if media_type == "movie" else owned_tv)
                if owned or t in reqd:
                    continue
                cands.append(
                    {
                        "type": media_type,
                        "title": r.get("title") or r.get("name"),
                        "year": str(r.get("releaseDate") or r.get("firstAirDate") or "")[:4],
                        "vote": r.get("voteAverage") or 0,
                        "overview": (r.get("overview") or "")[:130],
                    }
                )

    cands.sort(key=lambda x: -x["vote"])
    for c in cands[:15]:
        print(f"[{c['type']}] {c['title']} ({c['year']}) vote={c['vote']:.1f}")
        print(f"    {c['overview']}")
    print(f"\nTOTAL candidates: {len(cands)}")


if __name__ == "__main__":
    main()