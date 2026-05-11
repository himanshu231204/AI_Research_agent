"""
Browser Tool - Playwright-based browser automation
"""

import asyncio
import logging
import base64
from dataclasses import dataclass, field
from typing import Optional, Dict, Any, List
from datetime import datetime
from pathlib import Path

from playwright.async_api import async_playwright, Browser, Page, BrowserContext, Playwright

logger = logging.getLogger(__name__)


@dataclass
class BrowserConfig:
    """Browser configuration"""

    headless: bool = True
    viewport_width: int = 1920
    viewport_height: int = 1080
    user_agent: str = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"
    accept_downloads: bool = True
    ignore_https_errors: bool = True
    java_script_enabled: bool = True
    # Sandbox settings
    sandbox: bool = True
    # Proxy settings
    proxy_server: Optional[str] = None
    # Timeouts
    default_timeout: int = 30000
    navigation_timeout: int = 30000


@dataclass
class BrowserResult:
    """Result of browser operation"""

    success: bool
    data: Optional[Any] = None
    error: Optional[str] = None
    screenshot: Optional[str] = None  # Base64 encoded
    artifacts: List[str] = field(default_factory=list)
    execution_time: float = 0.0
    metadata: Dict[str, Any] = field(default_factory=dict)


class BrowserTool:
    """Playwright-based browser automation tool"""

    def __init__(self, config: BrowserConfig = None):
        self.config = config or BrowserConfig()
        self._playwright: Optional[Playwright] = None
        self._browser: Optional[Browser] = None
        self._context: Optional[BrowserContext] = None
        self._page: Optional[Page] = None
        self._session_id: Optional[str] = None

    async def start(self) -> bool:
        """Start browser"""
        try:
            self._playwright = await async_playwright().start()

            # Launch browser
            launch_options = {
                "headless": self.config.headless,
                "args": ["--no-sandbox", "--disable-setuid-sandbox"],
            }

            if self.config.proxy_server:
                launch_options["proxy"] = {"server": self.config.proxy_server}

            self._browser = await self._playwright.chromium.launch(**launch_options)

            # Create context
            context_options = {
                "viewport": {
                    "width": self.config.viewport_width,
                    "height": self.config.viewport_height,
                },
                "user_agent": self.config.user_agent,
                "accept_downloads": self.config.accept_downloads,
                "ignore_https_errors": self.config.ignore_https_errors,
                "java_script_enabled": self.config.java_script_enabled,
            }

            self._context = await self._browser.new_context(**context_options)

            # Create page
            self._page = await self._context.new_page()

            # Set timeouts
            self._page.set_default_timeout(self.config.default_timeout)

            self._session_id = str(datetime.utcnow().timestamp())
            logger.info(f"Browser started (session: {self._session_id})")
            return True

        except Exception as e:
            logger.error(f"Failed to start browser: {e}")
            return False

    async def stop(self) -> None:
        """Stop browser"""
        try:
            if self._page:
                await self._page.close()
            if self._context:
                await self._context.close()
            if self._browser:
                await self._browser.close()
            if self._playwright:
                await self._playwright.stop()

            logger.info("Browser stopped")

        except Exception as e:
            logger.error(f"Error stopping browser: {e}")

    async def navigate(self, url: str, wait_until: str = "load") -> BrowserResult:
        """Navigate to URL"""
        start_time = datetime.utcnow()

        if not self._page:
            return BrowserResult(success=False, error="Browser not started")

        try:
            response = await self._page.goto(url, wait_until=wait_until)

            execution_time = (datetime.utcnow() - start_time).total_seconds()

            return BrowserResult(
                success=True,
                data={
                    "url": self._page.url,
                    "title": await self._page.title(),
                    "status": response.status if response else None,
                },
                execution_time=execution_time,
                metadata={"wait_until": wait_until},
            )

        except Exception as e:
            execution_time = (datetime.utcnow() - start_time).total_seconds()
            return BrowserResult(
                success=False,
                error=str(e),
                execution_time=execution_time,
            )

    async def screenshot(self, full_page: bool = False, format: str = "png") -> BrowserResult:
        """Take screenshot"""
        start_time = datetime.utcnow()

        if not self._page:
            return BrowserResult(success=False, error="Browser not started")

        try:
            screenshot_bytes = await self._page.screenshot(full_page=full_page, type=format)
            screenshot_base64 = base64.b64encode(screenshot_bytes).decode()

            execution_time = (datetime.utcnow() - start_time).total_seconds()

            return BrowserResult(
                success=True,
                data={"format": format, "full_page": full_page},
                screenshot=screenshot_base64,
                execution_time=execution_time,
            )

        except Exception as e:
            execution_time = (datetime.utcnow() - start_time).total_seconds()
            return BrowserResult(
                success=False,
                error=str(e),
                execution_time=execution_time,
            )

    async def click(self, selector: str, button: str = "left") -> BrowserResult:
        """Click element"""
        start_time = datetime.utcnow()

        if not self._page:
            return BrowserResult(success=False, error="Browser not started")

        try:
            await self._page.click(selector, button=button)

            execution_time = (datetime.utcnow() - start_time).total_seconds()

            return BrowserResult(
                success=True,
                data={"selector": selector, "button": button},
                execution_time=execution_time,
            )

        except Exception as e:
            execution_time = (datetime.utcnow() - start_time).total_seconds()
            return BrowserResult(
                success=False,
                error=str(e),
                execution_time=execution_time,
            )

    async def type(self, selector: str, text: str, clear: bool = True) -> BrowserResult:
        """Type text into element"""
        start_time = datetime.utcnow()

        if not self._page:
            return BrowserResult(success=False, error="Browser not started")

        try:
            if clear:
                await self._page.fill(selector, text)
            else:
                await self._page.type(selector, text)

            execution_time = (datetime.utcnow() - start_time).total_seconds()

            return BrowserResult(
                success=True,
                data={"selector": selector, "text_length": len(text)},
                execution_time=execution_time,
            )

        except Exception as e:
            execution_time = (datetime.utcnow() - start_time).total_seconds()
            return BrowserResult(
                success=False,
                error=str(e),
                execution_time=execution_time,
            )

    async def evaluate(self, script: str) -> BrowserResult:
        """Execute JavaScript"""
        start_time = datetime.utcnow()

        if not self._page:
            return BrowserResult(success=False, error="Browser not started")

        try:
            result = await self._page.evaluate(script)

            execution_time = (datetime.utcnow() - start_time).total_seconds()

            return BrowserResult(
                success=True,
                data=result,
                execution_time=execution_time,
            )

        except Exception as e:
            execution_time = (datetime.utcnow() - start_time).total_seconds()
            return BrowserResult(
                success=False,
                error=str(e),
                execution_time=execution_time,
            )

    async def get_html(self) -> BrowserResult:
        """Get page HTML"""
        start_time = datetime.utcnow()

        if not self._page:
            return BrowserResult(success=False, error="Browser not started")

        try:
            html = await self._page.content()

            execution_time = (datetime.utcnow() - start_time).total_seconds()

            return BrowserResult(
                success=True,
                data={"html": html[:10000]},  # Limit size
                execution_time=execution_time,
            )

        except Exception as e:
            execution_time = (datetime.utcnow() - start_time).total_seconds()
            return BrowserResult(
                success=False,
                error=str(e),
                execution_time=execution_time,
            )

    async def wait_for_selector(self, selector: str, timeout: int = 30000) -> BrowserResult:
        """Wait for selector"""
        start_time = datetime.utcnow()

        if not self._page:
            return BrowserResult(success=False, error="Browser not started")

        try:
            await self._page.wait_for_selector(selector, timeout=timeout)

            execution_time = (datetime.utcnow() - start_time).total_seconds()

            return BrowserResult(
                success=True,
                data={"selector": selector},
                execution_time=execution_time,
            )

        except Exception as e:
            execution_time = (datetime.utcnow() - start_time).total_seconds()
            return BrowserResult(
                success=False,
                error=str(e),
                execution_time=execution_time,
            )

    async def get_title(self) -> Optional[str]:
        """Get page title"""
        if self._page:
            return await self._page.title()
        return None

    async def get_url(self) -> Optional[str]:
        """Get current URL"""
        if self._page:
            return self._page.url
        return None

    @property
    def session_id(self) -> Optional[str]:
        """Get session ID"""
        return self._session_id

    @property
    def is_running(self) -> bool:
        """Check if browser is running"""
        return self._browser is not None and self._page is not None
