from app.helper.sites import SitesHelper

SITE_URL = "https://m-team.vip/"
SITE_LABEL = "馒头"
SITE_HOST = "m-team.vip"
PROBE_PATH = "/api/local/user/me"

_DROP_KEYS = ("language", "subtitles", "api_domain", "api_host")


def register() -> None:
    _install_site_test()
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


def legacy_keys() -> tuple:
    return (SITE_HOST,)


def _token_of(site) -> str:
    token = str(getattr(site, "apikey", "") or "").strip()
    if token:
        return token
    cookie = str(getattr(site, "cookie", "") or "")
    for part in cookie.split(";"):
        name, _, value = part.partition("=")
        if name.strip() in ("mt_session", "mirror_session") and value.strip():
            return value.strip()
    return ""


def _site_base(site) -> str:
    candidate = str(getattr(site, "domain", "") or getattr(site, "url", "") or "")
    if SITE_HOST in candidate:
        return candidate.split(SITE_HOST, 1)[0] + SITE_HOST
    return SITE_URL.rstrip("/")


def _probe_legacy(site):
    from app.core.config import settings
    from app.utils.http import RequestUtils

    token = _token_of(site)
    if not token:
        return False, "未配置 API 密钥"
    headers = {"Accept": "application/json", "Authorization": f"Bearer {token}"}
    res = RequestUtils(
        headers=headers,
        proxies=settings.PROXY if getattr(site, "proxy", 0) else None,
        timeout=getattr(site, "timeout", 0) or 15,
    ).get_res(f"{_site_base(site)}{PROBE_PATH}")
    if res is None:
        return False, "无法连接 m-team.vip"
    status = getattr(res, "status_code", 0)
    if status == 200:
        return True, "连接成功"
    if status == 401:
        return False, "API 密钥无效或已撤销"
    if status == 403:
        return False, "账号被暂停或不可用"
    return False, f"错误：{status}"


def _install_site_test() -> None:
    try:
        from app.chain.site import SiteChain
    except Exception:
        return
    if getattr(SiteChain, "_mteamvip_site_test_patched", False):
        return
    original = SiteChain.__init__

    def __init__(self, *args, **kwargs):
        original(self, *args, **kwargs)
        try:
            for key in legacy_keys():
                self.special_site_test[key] = _probe_legacy
        except Exception:
            pass

    SiteChain.__init__ = __init__
    SiteChain._mteamvip_site_test_patched = True