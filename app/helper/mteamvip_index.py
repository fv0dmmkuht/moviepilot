from app.helper.sites import SitesHelper

SITE_URL = "https://m-team.vip/"
SITE_LABEL = "馒头"
SITE_HOST = "m-team.vip"
SITE_PARSER = "mTorrent"
SITE_SCHEMA = "MTorrent"
SITE_ID = 92001
PROBE_PATH = "/api/local/user/me"

_LEGACY_HOSTS = ("m-team.vip", "m-team.cc", "m-team.me", "mteam", "m-team")
_CARD_KEYS = ("cookie", "ua", "apikey", "token", "proxy", "timeout", "pri", "is_active")
_ORIG = {}
_ENTRY = {}


def register() -> None:
    for step in (_install, _install_site_test, _announce):
        try:
            step()
        except Exception:
            continue


def _host_of(domain) -> str:
    text = str(domain or "").strip()
    if "://" in text:
        text = text.split("://", 1)[1]
    return text.split("/", 1)[0].split(":", 1)[0].strip().lower()


def _is_boiled(item) -> bool:
    if not isinstance(item, dict):
        return False
    if item.get("name") == SITE_LABEL:
        return True
    return _host_of(item.get("domain") or item.get("url")) in _LEGACY_HOSTS


def _raw_indexers(helper) -> list:
    fn = _ORIG.get("list")
    if not fn:
        return []
    try:
        items = fn(helper)
    except Exception:
        return []
    return [item for item in (items or []) if isinstance(item, dict)]


def _raw_indexsites(helper) -> dict:
    fn = _ORIG.get("sites")
    if not fn:
        return {}
    try:
        sites = fn(helper)
    except Exception:
        return {}
    return sites if isinstance(sites, dict) else {}


def _card_fields() -> dict:
    try:
        from app.db.site_oper import SiteOper
    except Exception:
        return {}
    try:
        site = SiteOper().get_by_domain(SITE_HOST)
    except Exception:
        return {}
    if not site:
        return {}
    fields = {}
    for key in _CARD_KEYS:
        value = getattr(site, key, None)
        if value not in (None, ""):
            fields[key] = value
    return fields


def _legacy_id(helper) -> int:
    for item in _raw_indexers(helper):
        if item.get("name") == SITE_LABEL and item.get("id"):
            return item["id"]
    return SITE_ID


def _entry(helper=None) -> dict:
    helper = helper or SitesHelper()
    entry = {
        "id": _legacy_id(helper),
        "name": SITE_LABEL,
        "domain": SITE_HOST,
        "url": SITE_URL,
        "parser": SITE_PARSER,
        "schema": SITE_SCHEMA,
        "public": False,
        "pri": 1,
        "is_active": True,
    }
    entry.update(_card_fields())
    _ENTRY.clear()
    _ENTRY.update(entry)
    return dict(entry)


def _list_view(items: list, helper) -> list:
    kept = [item for item in items if not _is_boiled(item)]
    kept.insert(0, _entry(helper))
    return kept


def _sites_view(sites: dict, helper) -> dict:
    view = {key: value for key, value in sites.items() if not _is_boiled(value)}
    view[SITE_HOST] = {"id": SITE_ID, "name": SITE_LABEL, "domain": SITE_HOST,
                       "url": SITE_URL, "pri": 1}
    return view


def _install() -> None:
    if getattr(SitesHelper, "_mteamvip_index_patched", False):
        return
    original_get = SitesHelper.get_indexer
    original_async_get = SitesHelper.async_get_indexer
    original_list = getattr(SitesHelper, "get_indexers", None)
    original_async_list = getattr(SitesHelper, "async_get_indexers", None)
    original_sites = getattr(SitesHelper, "get_indexsites", None)

    _ORIG.update({"get": original_get, "aget": original_async_get,
                  "list": original_list, "alist": original_async_list,
                  "sites": original_sites})

    def get_indexer(self, domain):
        found = None
        try:
            found = original_get(self, domain)
        except Exception:
            found = None
        if _host_of(domain) in _LEGACY_HOSTS or _is_boiled(found):
            return _entry(self)
        return found

    async def async_get_indexer(self, domain):
        found = None
        try:
            found = await original_async_get(self, domain)
        except Exception:
            found = None
        if _host_of(domain) in _LEGACY_HOSTS or _is_boiled(found):
            return _entry(self)
        return found

    SitesHelper.get_indexer = get_indexer
    SitesHelper.async_get_indexer = async_get_indexer

    if original_list is not None:
        def get_indexers(self, *args, **kwargs):
            items = original_list(self, *args, **kwargs)
            try:
                return _list_view(list(items or []), self)
            except Exception:
                return items

        SitesHelper.get_indexers = get_indexers

    if original_async_list is not None:
        async def async_get_indexers(self, *args, **kwargs):
            items = await original_async_list(self, *args, **kwargs)
            try:
                return _list_view(list(items or []), self)
            except Exception:
                return items

        SitesHelper.async_get_indexers = async_get_indexers

    if original_sites is not None:
        def get_indexsites(self, *args, **kwargs):
            sites = original_sites(self, *args, **kwargs)
            try:
                return _sites_view(sites or {}, self)
            except Exception:
                return sites

        SitesHelper.get_indexsites = get_indexsites

    SitesHelper._mteamvip_index_patched = True
    _entry(SitesHelper())


def _announce() -> None:
    from app.log import logger

    entry = dict(_ENTRY)
    logger.info(
        "站点 %s 已接管：%s parser=%s schema=%s cookie=%s",
        entry.get("name"), entry.get("url"), entry.get("parser"),
        entry.get("schema"), "yes" if entry.get("cookie") else "no",
    )


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
            self.special_site_test[SITE_HOST] = _probe_legacy
        except Exception:
            pass

    SiteChain.__init__ = __init__
    SiteChain._mteamvip_site_test_patched = True