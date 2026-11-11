import re
from datetime import datetime
from typing import List, Optional, Tuple

from app.core.config import settings
from app.log import logger
from app.schemas import MediaType
from app.utils.http import AsyncRequestUtils, RequestUtils


class MTorrentSpider:

    _default_site = "https://m-team.vip/"
    _size = 100
    _timeout = 15

    _movie_category = ['401', '419', '420', '421', '439', '405', '404']
    _tv_category = ['403', '402', '435', '438', '404', '405']

    _download_factor = {
        "FREE": 0.0,
        "2X_FREE": 0.0,
        "PERCENT_50": 0.5,
        "PERCENT_30": 0.3,
    }
    _upload_factor = {
        "2X": 2.0,
        "2X_FREE": 2.0,
        "2X_UP": 2.0,
    }

    def __init__(self, indexer: dict):
        indexer = indexer or {}
        self._name = indexer.get("name") or ""
        candidate = str(indexer.get("domain") or indexer.get("url") or "")
        self._base = (candidate if "m-team.vip" in candidate else self._default_site).rstrip("/")
        self._cookie = indexer.get("cookie")
        self._ua = indexer.get("ua")
        self._proxy = settings.PROXY if indexer.get("proxy") else None
        self._timeout = indexer.get("timeout") or self._timeout
        self.error_detail: Optional[str] = None

    @classmethod
    def get_search_page_size(cls, keyword: Optional[str] = None) -> Optional[int]:
        return cls._size

    def _params(self, keyword: Optional[str], mtype: Optional[MediaType],
                cat: Optional[str], page: Optional[int]) -> dict:
        if cat:
            categories = [c.strip() for c in str(cat).split(",") if c.strip()]
        elif not mtype:
            categories = []
        elif mtype == MediaType.TV:
            categories = self._tv_category
        else:
            categories = self._movie_category
        words = keyword or ""
        if words.startswith("tt"):
            words = f"https://www.imdb.com/title/{words}"
        return {
            "q": words,
            "cat": ",".join(categories),
            "page": int(page or 0) + 1,
            "page_size": self._size,
        }

    def _http_kwargs(self) -> dict:
        headers = {"Accept": "application/json"}
        if self._ua:
            headers["User-Agent"] = self._ua
        return {
            "headers": headers,
            "cookies": self._cookie,
            "proxies": self._proxy,
            "timeout": self._timeout,
        }

    def _url(self) -> str:
        return f"{self._base}/api/local/torrents"

    def search(self, keyword: Optional[str], mtype: Optional[MediaType] = None,
               cat: Optional[str] = None, page: Optional[int] = 0) -> Tuple[bool, List[dict]]:
        if not self._base:
            self.error_detail = "站点地址为空"
            return True, []
        res = RequestUtils(**self._http_kwargs()).get_res(
            self._url(), params=self._params(keyword, mtype, cat, page)
        )
        return self._process(res)

    async def async_search(self, keyword: Optional[str], mtype: Optional[MediaType] = None,
                           cat: Optional[str] = None, page: Optional[int] = 0) -> Tuple[bool, List[dict]]:
        if not self._base:
            self.error_detail = "站点地址为空"
            return True, []
        res = await AsyncRequestUtils(**self._http_kwargs()).get_res(
            self._url(), params=self._params(keyword, mtype, cat, page)
        )
        return self._process(res)

    def _process(self, res) -> Tuple[bool, List[dict]]:
        self.error_detail = None
        if res is None:
            self.error_detail = f"无法连接 {self._base}"
            logger.warning(f"{self._name} 搜索失败：{self.error_detail}")
            return True, []
        status_code = getattr(res, "status_code", 0)
        if status_code != 200:
            self.error_detail = f"HTTP {status_code}"
            logger.warning(f"{self._name} 搜索失败，错误码：{status_code}")
            return True, []
        try:
            payload = res.json()
        except Exception as err:
            self.error_detail = "响应不是合法 JSON"
            logger.warning(f"{self._name} 搜索失败：{self.error_detail}（{err}）")
            return True, []
        data = (payload or {}).get("data") or {}
        torrents = []
        for item in data.get("items") or []:
            mapped = self._map(item)
            if mapped:
                torrents.append(mapped)
        return False, torrents

    def _map(self, item: dict) -> Optional[dict]:
        if not isinstance(item, dict):
            return None
        tid = item.get("id")
        if tid in (None, ""):
            return None
        status = item.get("status") or {}
        discount = str(status.get("discount") or "").upper()
        category = str(item.get("category") or "")
        if category in self._tv_category and category not in self._movie_category:
            media_type = MediaType.TV.value
        elif category in self._movie_category:
            media_type = MediaType.MOVIE.value
        else:
            media_type = MediaType.UNKNOWN.value
        labels = [str(x) for x in (item.get("labels") or []) if x]
        if item.get("has_chinese_subtitle") and "中字" not in labels:
            labels.append("中字")
        torrent = {
            "title": item.get("name"),
            "description": item.get("small_descr"),
            "enclosure": f"{self._base}/api/local/torrents/{tid}/file",
            "pubdate": self._format_time(item.get("created_at")),
            "size": int(item.get("size_bytes") or 0),
            "seeders": int(status.get("seeders") or 0),
            "peers": int(status.get("leechers") or 0),
            "grabs": int(status.get("completed") or 0),
            "downloadvolumefactor": self._download_factor.get(discount, 1.0),
            "uploadvolumefactor": self._upload_factor.get(discount, 1.0),
            "page_url": f"{self._base}/torrent/{tid}",
            "imdbid": self._find_imdbid(item.get("imdb")),
            "labels": labels,
            "category": media_type,
        }
        if discount_end := status.get("discount_end_time"):
            torrent["freedate"] = self._format_time(discount_end)
        return torrent

    @staticmethod
    def _format_time(value) -> Optional[str]:
        if value in (None, ""):
            return None
        if isinstance(value, (int, float)):
            seconds = float(value)
            if seconds > 1e12:
                seconds /= 1000.0
            return datetime.fromtimestamp(seconds).strftime("%Y-%m-%d %H:%M:%S")
        text = str(value).strip()
        if text.isdigit():
            return MTorrentSpider._format_time(int(text))
        try:
            parsed = datetime.fromisoformat(text.replace("Z", "+00:00"))
        except ValueError:
            return text
        if parsed.tzinfo is not None:
            parsed = parsed.astimezone()
        return parsed.strftime("%Y-%m-%d %H:%M:%S")

    @staticmethod
    def _find_imdbid(imdb: Optional[str]) -> str:
        if not imdb:
            return ""
        found = re.search(r"tt\d+", str(imdb))
        return found.group(0) if found else ""

    def get_subtitle_links(self, page_url: str) -> List[str]:
        return []

    def get_subtitle_links_by_id(self, torrent_id: str) -> List[str]:
        return []