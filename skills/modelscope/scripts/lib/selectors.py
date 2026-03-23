from dataclasses import dataclass

BASE_URL = "https://www.modelscope.cn"
MODEL_PAGE_URL = BASE_URL + "/models/{model_slug}"
MODEL_FILES_PAGE_URL = BASE_URL + "/models/{model_slug}/files"
LOGIN_INFO_API = BASE_URL + "/api/v1/users/login/info"
TOKEN_CREATE_API = BASE_URL + "/api/v1/users/tokens"
TOKEN_LIST_API = BASE_URL + "/api/v1/users/tokens/list"
SEARCH_MODELS_API = BASE_URL + "/api/v1/dolphin/models"
MODEL_REPO_FILES_API = BASE_URL + "/api/v1/models/{model_slug}/repo/files"
MODEL_REVISIONS_API = BASE_URL + "/api/v1/models/{model_slug}/revisions"

EMBEDDED_DETAIL_MARKER = "window.__detail_data__ = "


@dataclass(frozen=True)
class PageSelectors:
    page_title: str
    heading: str
    login_button: str
    login_dialog: str
    login_iframe: str


MODEL_DETAIL_SELECTORS = PageSelectors(
    page_title="h1",
    heading="h1",
    login_button="button:has-text('login / register')",
    login_dialog='[role="dialog"]',
    login_iframe="iframe#alibaba-login-box",
)
