#!/usr/bin/env python3
"""
Browser Sandbox Server

Provides an isolated environment for browser automation using Playwright.
This server exposes a simple API for browser operations.
"""

import asyncio
import json
import logging
import os
import sys
from pathlib import Path
from typing import Optional

from playwright.async_api import async_playwright, Browser, BrowserContext, Page

logging.basicConfig(
    level=logging.INFO, format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger(__name__)

SANDBOX_MODE = os.getenv("SANDBOX_MODE", "true").lower() == "true"
PORT = int(os.getenv("PORT", "9222"))


class BrowserSandbox:
    """Manages browser instances in isolated sandbox."""

    def __init__(self):
        self.playwright = None
        self.browser: Optional[Browser] = None
        self.contexts: dict[str, BrowserContext] = {}

    async def initialize(self):
        """Initialize Playwright and browser."""
        logger.info("Initializing browser sandbox...")
        self.playwright = await async_playwright().start()

        # Launch browser with sandbox restrictions
        self.browser = await self.playwright.chromium.launch(
            headless=True,
            args=[
                "--no-sandbox",
                "--disable-setuid-sandbox",
                "--disable-dev-shm-usage",
                "--disable-gpu",
                "--disable-software-rasterizer",
                "--disable-extensions",
                "--disable-background-networking",
                "--disable-default-apps",
                "--disable-sync",
                "--disable-translate",
                "--metrics-recording-only",
                "--mute-audio",
                "--no-first-run",
                "--safebrowsing-disable-auto-update",
            ]
            if SANDBOX_MODE
            else [],
        )
        logger.info("Browser sandbox initialized")

    async def create_context(self, context_id: str) -> dict:
        """Create a new browser context."""
        if context_id in self.contexts:
            return {"status": "error", "message": f"Context {context_id} already exists"}

        context = await self.browser.new_context(
            viewport={"width": 1280, "height": 720},
            ignore_https_errors=True,
        )
        self.contexts[context_id] = context

        return {"status": "success", "context_id": context_id}

    async def close_context(self, context_id: str) -> dict:
        """Close a browser context."""
        if context_id not in self.contexts:
            return {"status": "error", "message": f"Context {context_id} not found"}

        await self.contexts[context_id].close()
        del self.contexts[context_id]

        return {"status": "success", "context_id": context_id}

    async def navigate(self, context_id: str, url: str) -> dict:
        """Navigate to a URL in the given context."""
        if context_id not in self.contexts:
            return {"status": "error", "message": f"Context {context_id} not found"}

        try:
            page = await self.contexts[context_id].new_page()
            response = await page.goto(url, wait_until="domcontentloaded")

            content = await page.content()
            title = await page.title()

            await page.close()

            return {
                "status": "success",
                "url": url,
                "title": title,
                "status_code": response.status if response else None,
                "content_length": len(content),
            }
        except Exception as e:
            logger.error(f"Navigation error: {e}")
            return {"status": "error", "message": str(e)}

    async def execute_script(self, context_id: str, script: str) -> dict:
        """Execute JavaScript in the given context."""
        if context_id not in self.contexts:
            return {"status": "error", "message": f"Context {context_id} not found"}

        try:
            page = await self.contexts[context_id].new_page()
            result = await page.evaluate(script)
            await page.close()

            return {"status": "success", "result": result}
        except Exception as e:
            logger.error(f"Script execution error: {e}")
            return {"status": "error", "message": str(e)}

    async def health_check(self) -> dict:
        """Health check endpoint."""
        return {
            "status": "healthy",
            "sandbox_mode": SANDBOX_MODE,
            "active_contexts": len(self.contexts),
            "browser_version": self.browser.version if self.browser else None,
        }

    async def shutdown(self):
        """Shutdown the browser sandbox."""
        logger.info("Shutting down browser sandbox...")

        for context in self.contexts.values():
            await context.close()
        self.contexts.clear()

        if self.browser:
            await self.browser.close()

        if self.playwright:
            await self.playwright.stop()

        logger.info("Browser sandbox shutdown complete")


# Global sandbox instance
sandbox: Optional[BrowserSandbox] = None


async def handle_request(method: str, path: str, body: Optional[dict] = None) -> dict:
    """Handle incoming HTTP requests."""
    global sandbox

    # Health check
    if path == "/health" or path == "/":
        return await sandbox.health_check()

    # API endpoints
    if path == "/api/v1/contexts" and method == "POST":
        context_id = body.get("context_id") if body else None
        if not context_id:
            return {"status": "error", "message": "context_id required"}
        return await sandbox.create_context(context_id)

    if path.startswith("/api/v1/contexts/") and method == "DELETE":
        context_id = path.split("/")[-1]
        return await sandbox.close_context(context_id)

    if path.startswith("/api/v1/navigate/") and method == "POST":
        parts = path.split("/")
        context_id = parts[-2]
        url = body.get("url") if body else None
        if not url:
            return {"status": "error", "message": "url required"}
        return await sandbox.navigate(context_id, url)

    if path.startswith("/api/v1/script/") and method == "POST":
        parts = path.split("/")
        context_id = parts[-2]
        script = body.get("script") if body else None
        if not script:
            return {"status": "error", "message": "script required"}
        return await sandbox.execute_script(context_id, script)

    # Debug endpoint
    if path == "/json/version":
        return {
            "Browser": f"Chrome/{sandbox.browser.version if sandbox.browser else 'unknown'}",
            "Protocol-Version": "1.3",
        }

    return {"status": "error", "message": "Not found"}


async def main():
    """Main entry point."""
    global sandbox

    try:
        sandbox = BrowserSandbox()
        await sandbox.initialize()

        logger.info(f"Browser sandbox server running on port {PORT}")
        logger.info(f"Sandbox mode: {SANDBOX_MODE}")

        # Simple HTTP server using asyncio
        server = await asyncio.start_server(lambda r, w: handle_http_request(r, w), "0.0.0.0", PORT)

        async with server:
            await server.serve_forever()

    except KeyboardInterrupt:
        logger.info("Received shutdown signal")
    finally:
        if sandbox:
            await sandbox.shutdown()


async def handle_http_request(reader, writer):
    """Handle HTTP request."""
    try:
        data = await reader.read(4096)
        if not data:
            return

        request = data.decode("utf-8")
        lines = request.split("\r\n")

        if not lines:
            return

        # Parse request line
        parts = lines[0].split()
        if len(parts) < 2:
            return

        method = parts[0]
        path = parts[1]

        # Parse body if present
        body = None
        if "Content-Length:" in request:
            for line in lines:
                if line.startswith("Content-Length:"):
                    content_length = int(line.split(":")[1].strip())
                    body_start = request.find("\r\n\r\n") + 4
                    if body_start > 3 and content_length > 0:
                        body_str = request[body_start : body_start + content_length]
                        try:
                            body = json.loads(body_str)
                        except:
                            pass

        # Handle request
        response = await handle_request(method, path, body)

        # Send response
        response_body = json.dumps(response)
        writer.write(b"HTTP/1.1 200 OK\r\n")
        writer.write(b"Content-Type: application/json\r\n")
        writer.write(f"Content-Length: {len(response_body)}\r\n".encode())
        writer.write(b"Access-Control-Allow-Origin: *\r\n")
        writer.write(b"\r\n")
        writer.write(response_body.encode())

    except Exception as e:
        logger.error(f"HTTP request error: {e}")
    finally:
        writer.close()


if __name__ == "__main__":
    asyncio.run(main())
