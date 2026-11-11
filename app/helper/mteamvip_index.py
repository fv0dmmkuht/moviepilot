from app.helper.sites import SitesHelper

SITE_URL = "https://m-team.vip/"
SITE_LABEL = "馒头"

_DROP_KEYS = ("language", "subtitles", "api_domain", "api_host")


def register() -> None:
    try:
        helper = SitesHelper()
        sites = helper.get_indexsites() or {}
        if not isinstance(sites, dict):
            return
        keys = [k for k, v in sites.items()
                if isinstance(v, dict) and v.get("name") == SITE_LABEL]
        if keys:
            for key in keys:
                entry = dict(sites[key])
                entry["domain"] = SITE_URL
                entry["url"] = SITE_URL
                for drop in _DROP_KEYS:
                    entry.pop(drop, None)
                helper.add_indexer(key, entry)
            return
        helper.add_indexer("m-team.vip", {
            "id": 92001,
            "name": SITE_LABEL,
            "domain": SITE_URL,
            "url": SITE_URL,
            "parser": "mTorrent",
            "schema": "MTorrent",
            "public": False,
            "pri": 1,
        })
    except Exception:
        return