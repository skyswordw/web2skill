from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from playwright.async_api import Browser, BrowserContext, Page, Playwright, async_playwright


@dataclass(slots=True, frozen=True)
class BrowserSessionConfig:
    headless: bool = True
    storage_state_path: Path | None = None
    base_url: str | None = None


class BrowserClient:
    def __init__(self, config: BrowserSessionConfig | None = None) -> None:
        self.config = config or BrowserSessionConfig()
        self._playwright: Playwright | None = None
        self._browser: Browser | None = None
        self._context: BrowserContext | None = None

    async def __aenter__(self) -> BrowserClient:
        self._playwright = await async_playwright().start()
        self._browser = await self._playwright.chromium.launch(headless=self.config.headless)
        storage_state: str | None = None
        if self.config.storage_state_path is not None and self.config.storage_state_path.exists():
            storage_state = str(self.config.storage_state_path)
        self._context = await self._browser.new_context(
            base_url=self.config.base_url,
            storage_state=storage_state,
        )
        return self

    async def __aexit__(self, exc_type: object, exc: object, tb: object) -> None:
        if self._context is not None:
            await self._context.close()
        if self._browser is not None:
            await self._browser.close()
        if self._playwright is not None:
            await self._playwright.stop()

    @property
    def context(self) -> BrowserContext:
        if self._context is None:
            msg = "BrowserClient has not been entered yet."
            raise RuntimeError(msg)
        return self._context

    async def new_page(self) -> Page:
        return await self.context.new_page()

    async def persist_storage_state(self, path: Path | None = None) -> Path | None:
        target = path or self.config.storage_state_path
        if target is None:
            return None
        target.parent.mkdir(parents=True, exist_ok=True)
        await self.context.storage_state(path=str(target))
        return target
