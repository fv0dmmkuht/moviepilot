AUTH_LEVEL = 2
AUTH_SOURCE = "m-team.vip"


def _patch_sites_helper() -> bool:
    try:
        from app.helper.sites import SitesHelper
    except Exception:
        return False
    if getattr(SitesHelper, "_mteamvip_auth_patched", False):
        return True

    def auth_level(self) -> int:
        return AUTH_LEVEL

    def auth_level_setter(self, value) -> None:
        pass

    def check_user(self, *args, **kwargs):
        return True, AUTH_SOURCE

    SitesHelper.auth_level = property(auth_level, auth_level_setter)
    SitesHelper.check_user = check_user
    SitesHelper._mteamvip_auth_patched = True
    return True


def _disable_startup_auth() -> None:
    try:
        from app.startup import modules_initializer
    except Exception:
        return
    if getattr(modules_initializer, "_mteamvip_auth_disabled", False):
        return
    modules_initializer.user_auth = lambda *args, **kwargs: None
    modules_initializer.check_auth = lambda *args, **kwargs: None
    modules_initializer._mteamvip_auth_disabled = True


def register() -> None:
    if not _patch_sites_helper():
        return
    _disable_startup_auth()