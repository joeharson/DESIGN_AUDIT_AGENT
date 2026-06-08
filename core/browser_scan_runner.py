"""Playwright browser automation for Level 3 scans."""

from __future__ import annotations

import time
from pathlib import Path

from core.regression_scan_contracts import AuthConfig, PageConfig
from utils.structured_event_logging import get_logger

logger = get_logger(__name__)


class BrowserManager:
    def __init__(
        self,
        viewport_width: int,
        viewport_height: int,
        headless: bool = True,
        wait_after_navigation_ms: int = 2000,
    ) -> None:
        self.viewport_width = viewport_width
        self.viewport_height = viewport_height
        self.headless = headless
        self.wait_after_navigation_ms = wait_after_navigation_ms
        self._playwright = None
        self.browser = None
        self.context = None
        self.page = None

    async def start(self) -> None:
        from playwright.async_api import async_playwright

        try:
            self._playwright = await async_playwright().start()
        except NotImplementedError as exc:
            raise RuntimeError(
                "Playwright could not start because the Windows asyncio event loop does not support subprocesses. "
                "Restart FastAPI after this fix, and start it from a normal terminal with: "
                "uvicorn main:app --reload --port 8001"
            ) from exc
        self.browser = await self._playwright.chromium.launch(headless=self.headless)
        self.context = await self.browser.new_context(
            viewport={"width": self.viewport_width, "height": self.viewport_height},
            ignore_https_errors=True,
            user_agent=(
                "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
                "Chrome/124.0.0.0 Safari/537.36 DesignAuditAgent/3.0"
            ),
        )
        self.page = await self.context.new_page()
        self.page.set_default_timeout(10000)
        logger.info("browser launched", extra={"viewport": f"{self.viewport_width}x{self.viewport_height}"})

    async def stop(self) -> None:
        try:
            if self.context:
                await self.context.close()
            if self.browser:
                await self.browser.close()
            if self._playwright:
                await self._playwright.stop()
            logger.info("browser stopped")
        except Exception as exc:
            logger.warning("browser shutdown failed", extra={"error": str(exc)})

    async def authenticate(self, auth_config: AuthConfig) -> bool:
        try:
            logger.info("auth navigation started", extra={"login_url": auth_config.login_url})
            await self.page.goto(auth_config.login_url, wait_until="domcontentloaded", timeout=20000)
            await self.page.wait_for_selector(auth_config.username_selector, state="visible")
            await self.page.fill(auth_config.username_selector, auth_config.username)
            await self.page.fill(auth_config.password_selector, auth_config.password)
            await self.page.click(auth_config.submit_selector)
            await self.page.wait_for_selector(auth_config.success_indicator, timeout=10000)
            logger.info("authentication succeeded")
            return True
        except Exception as exc:
            logger.warning("authentication failed", extra={"error": str(exc)})
            return False

    async def navigate_and_capture(self, page_config: PageConfig, output_dir: str) -> dict:
        try:
            Path(output_dir).mkdir(parents=True, exist_ok=True)
            await self.page.goto(page_config.url, wait_until="domcontentloaded", timeout=20000)
            try:
                await self.page.wait_for_load_state("networkidle", timeout=3000)
            except Exception:
                logger.info("network idle wait skipped", extra={"page_id": page_config.page_id})
            if self.wait_after_navigation_ms:
                await self.page.wait_for_timeout(self.wait_after_navigation_ms)
            if page_config.wait_for_selector:
                try:
                    await self.page.wait_for_selector(page_config.wait_for_selector, timeout=10000)
                except Exception as exc:
                    logger.warning("wait selector missing", extra={"page_id": page_config.page_id, "error": str(exc)})
            if page_config.scroll_to_top:
                await self.page.evaluate("window.scrollTo(0, 0)")
            masked = await self.mask_dynamic_regions(page_config)
            timestamp = time.strftime("%Y%m%d%H%M%S")
            screenshot_path = str(Path(output_dir) / f"{page_config.page_id}_{timestamp}.png")
            await self.page.screenshot(path=screenshot_path, full_page=False)
            title = await self.page.title()
            return {
                "screenshot_path": screenshot_path,
                "page_title": title,
                "success": True,
                "error": None,
                "dynamic_regions_filtered": masked,
            }
        except Exception as exc:
            logger.warning("page capture failed", extra={"page_id": page_config.page_id, "error": str(exc)})
            return {"screenshot_path": "", "page_title": "", "success": False, "error": str(exc), "dynamic_regions_filtered": 0}

    async def mask_dynamic_regions(self, page_config: PageConfig) -> int:
        masked = 0
        for selector in page_config.dynamic_selectors:
            try:
                count = await self.page.evaluate(
                    """
                    (selector) => {
                      const nodes = Array.from(document.querySelectorAll(selector));
                      for (const node of nodes) {
                        const rect = node.getBoundingClientRect();
                        if (!rect.width || !rect.height) continue;
                        const mask = document.createElement('div');
                        mask.setAttribute('data-design-audit-mask', selector);
                        Object.assign(mask.style, {
                          position: 'fixed',
                          left: `${rect.left}px`,
                          top: `${rect.top}px`,
                          width: `${rect.width}px`,
                          height: `${rect.height}px`,
                          background: '#808080',
                          zIndex: '2147483647',
                          pointerEvents: 'none'
                        });
                        document.body.appendChild(mask);
                      }
                      return nodes.length;
                    }
                    """,
                    selector,
                )
                masked += int(count or 0)
                if not count:
                    logger.info("dynamic selector not found", extra={"selector": selector})
            except Exception as exc:
                logger.info("dynamic selector skipped", extra={"selector": selector, "error": str(exc)})
        return masked
