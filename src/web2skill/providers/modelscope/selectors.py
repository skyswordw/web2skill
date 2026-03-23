from dataclasses import dataclass

BASE_URL = "https://www.modelscope.cn"
MODEL_PAGE_URL = BASE_URL + "/models/{model_slug}"
MODEL_FILES_PAGE_URL = BASE_URL + "/models/{model_slug}/files"
MODEL_SEARCH_PAGE_URL = BASE_URL + "/models"
LOGIN_INFO_API = BASE_URL + "/api/v1/users/login/info"
TOKEN_CREATE_API = BASE_URL + "/api/v1/users/tokens"
TOKEN_LIST_API = BASE_URL + "/api/v1/users/tokens/list"
SEARCH_MODELS_API = BASE_URL + "/api/v1/dolphin/models"
SEARCH_SUGGEST_API = BASE_URL + "/api/v1/dolphin/model/suggestv2"
MODEL_REPO_FILES_API = BASE_URL + "/api/v1/models/{model_slug}/repo/files"
MODEL_REVISIONS_API = BASE_URL + "/api/v1/models/{model_slug}/revisions"
MODEL_COMMITS_API = BASE_URL + "/api/v1/models/{model_slug}/commits"

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

MODEL_DETAIL_TABS = (
    '[role="tab"]:has-text("Model card")',
    '[role="tab"]:has-text("Files and versions")',
    '[role="tab"]:has-text("Discussions")',
)

SEARCH_PAGE_RESULT_LINKS = 'a[href^="/models/"]'
SEARCH_PAGE_QUERY_INPUT = 'input[placeholder*="Search models"]'
SEARCH_PAGE_TOP_SEARCH_INPUT = 'input[placeholder="Search anything..."]'
