from typing import Optional, Tuple

from app.core.config import settings
from app.log import logger
from app.modules.indexer.parser import SiteParserBase, SiteSchema
from app.utils.http import RequestUtils


class MTorrentSiteUserInfo(SiteParserBase):

    schema = SiteSchema.MTorrent
    request_mode = "cookie"

    _default_site = "https://m-team.vip/"

    def _site_base(self) -> str:
        candidate = str(self._site_url or "")
        if "m-team.vip" in candidate:
            return candidate.rstrip("/")
        return self._default_site.rstrip("/")

    def parse(self):
        if not self._site_cookie:
            self.err_msg = "未配置站点 Cookie"
            logger.warning(f"{self._site_name} {self.err_msg}")
            return
        headers = {"Accept": "application/json"}
        if self._ua:
            headers["User-Agent"] = self._ua
        url = f"{self._site_base()}/api/local/mp/userdata"
        res = RequestUtils(
            headers=headers,
            cookies=self._site_cookie,
            proxies=settings.PROXY if self._proxy else None,
            timeout=20,
        ).get_res(url)
        if res is None:
            self.err_msg = f"无法连接 {url}"
            logger.warning(f"{self._site_name} 站点数据获取失败：{self.err_msg}")
            return
        status_code = getattr(res, "status_code", 0)
        if status_code != 200:
            self.err_msg = f"站点数据获取失败（HTTP {status_code}）"
            logger.warning(f"{self._site_name} {self.err_msg}")
            return
        try:
            payload = res.json()
        except Exception as err:
            self.err_msg = "站点数据不是合法 JSON"
            logger.error(f"{self._site_name} {self.err_msg}：{err}")
            return
        data = (payload or {}).get("data") or {}
        if not data:
            self.err_msg = "站点数据为空"
            logger.warning(f"{self._site_name} {self.err_msg}")
            return
        self.userid = data.get("uid")
        self.username = data.get("username")
        self.user_level = data.get("role_label")
        self.join_at = data.get("created_at")
        self.upload = int(data.get("uploaded_bytes") or 0)
        self.download = int(data.get("downloaded_bytes") or 0)
        ratio = float(data.get("ratio") or 0)
        self.ratio = 0.0 if ratio < 0 else ratio
        self.bonus = float(data.get("bonus") or 0)
        self.seeding = int(data.get("seeding") or 0)
        self.leeching = int(data.get("leeching") or 0)
        self.seeding_size = int(data.get("seeding_size_bytes") or 0)
        self.leeching_size = int(data.get("leeching_size_bytes") or 0)
        self.message_unread = int(data.get("unread_messages") or 0) + \
            int(data.get("unread_notices") or 0)

    def _parse_logged_in(self, html_text) -> bool:
        return True

    def _parse_site_page(self, html_text: str) -> None:
        pass

    def _parse_user_base_info(self, html_text: str) -> None:
        pass

    def _parse_user_traffic_info(self, html_text: str) -> None:
        pass

    def _parse_user_detail_info(self, html_text: str) -> None:
        pass

    def _parse_user_torrent_seeding_info(self, html_text: str,
                                         multi_page: bool = False) -> Optional[str]:
        return None

    def _parse_message_unread_links(self, html_text: str, msg_links: list) -> Optional[str]:
        return None

    def _parse_message_content(self, html_text) -> Tuple[Optional[str], Optional[str], Optional[str]]:
        return None, None, None