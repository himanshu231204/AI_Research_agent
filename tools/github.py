"""
GitHub Tool - GitHub API integration
"""

import asyncio
import logging
from dataclasses import dataclass, field
from typing import Optional, Dict, Any, List
from datetime import datetime

import aiohttp

logger = logging.getLogger(__name__)


@dataclass
class GitHubConfig:
    """GitHub configuration"""

    token: str = ""
    base_url: str = "https://api.github.com"
    per_page: int = 30
    timeout: int = 30


@dataclass
class GitHubResult:
    """Result of GitHub operation"""

    success: bool
    data: Optional[Any] = None
    error: Optional[str] = None
    execution_time: float = 0.0
    metadata: Dict[str, Any] = field(default_factory=dict)


class GitHubTool:
    """GitHub API integration tool"""

    def __init__(self, config: GitHubConfig = None):
        self.config = config or GitHubConfig()
        self._session: Optional[aiohttp.ClientSession] = None

    async def _get_session(self) -> aiohttp.ClientSession:
        """Get or create HTTP session"""
        if self._session is None or self._session.closed:
            headers = {
                "Accept": "application/vnd.github.v3+json",
            }
            if self.config.token:
                headers["Authorization"] = f"token {self.config.token}"

            timeout = aiohttp.ClientTimeout(total=self.config.timeout)
            self._session = aiohttp.ClientSession(headers=headers, timeout=timeout)

        return self._session

    async def close(self) -> None:
        """Close HTTP session"""
        if self._session and not self._session.closed:
            await self._session.close()

    async def search_repos(
        self, query: str, sort: str = "stars", order: str = "desc", per_page: int = None
    ) -> GitHubResult:
        """Search repositories"""
        start_time = datetime.utcnow()
        per_page = per_page or self.config.per_page

        try:
            session = await self._get_session()

            url = f"{self.config.base_url}/search/repositories"
            params = {
                "q": query,
                "sort": sort,
                "order": order,
                "per_page": per_page,
            }

            async with session.get(url, params=params) as response:
                if response.status == 200:
                    data = await response.json()

                    execution_time = (datetime.utcnow() - start_time).total_seconds()

                    repos = [
                        {
                            "name": repo["full_name"],
                            "description": repo.get("description"),
                            "stars": repo["stargazers_count"],
                            "forks": repo["forks_count"],
                            "language": repo.get("language"),
                            "url": repo["html_url"],
                            "updated": repo.get("updated_at"),
                        }
                        for repo in data.get("items", [])
                    ]

                    return GitHubResult(
                        success=True,
                        data={
                            "total_count": data.get("total_count", 0),
                            "repos": repos,
                        },
                        execution_time=execution_time,
                    )
                else:
                    error_text = await response.text()
                    execution_time = (datetime.utcnow() - start_time).total_seconds()
                    return GitHubResult(
                        success=False,
                        error=f"GitHub API error: {response.status} - {error_text}",
                        execution_time=execution_time,
                    )

        except Exception as e:
            execution_time = (datetime.utcnow() - start_time).total_seconds()
            return GitHubResult(
                success=False,
                error=str(e),
                execution_time=execution_time,
            )

    async def get_file(self, owner: str, repo: str, path: str, ref: str = "main") -> GitHubResult:
        """Get file contents"""
        start_time = datetime.utcnow()

        try:
            session = await self._get_session()

            url = f"{self.config.base_url}/repos/{owner}/{repo}/contents/{path}"
            params = {"ref": ref}

            async with session.get(url, params=params) as response:
                if response.status == 200:
                    data = await response.json()

                    execution_time = (datetime.utcnow() - start_time).total_seconds()

                    # Decode content if base64 encoded
                    content = data.get("content", "")
                    if data.get("encoding") == "base64":
                        import base64

                        content = base64.b64decode(content).decode("utf-8")

                    return GitHubResult(
                        success=True,
                        data={
                            "name": data.get("name"),
                            "path": data.get("path"),
                            "size": data.get("size"),
                            "content": content,
                            "sha": data.get("sha"),
                            "url": data.get("html_url"),
                        },
                        execution_time=execution_time,
                    )
                elif response.status == 404:
                    execution_time = (datetime.utcnow() - start_time).total_seconds()
                    return GitHubResult(
                        success=False,
                        error=f"File not found: {path}",
                        execution_time=execution_time,
                    )
                else:
                    error_text = await response.text()
                    execution_time = (datetime.utcnow() - start_time).total_seconds()
                    return GitHubResult(
                        success=False,
                        error=f"GitHub API error: {response.status} - {error_text}",
                        execution_time=execution_time,
                    )

        except Exception as e:
            execution_time = (datetime.utcnow() - start_time).total_seconds()
            return GitHubResult(
                success=False,
                error=str(e),
                execution_time=execution_time,
            )

    async def list_files(
        self, owner: str, repo: str, path: str = "", ref: str = "main"
    ) -> GitHubResult:
        """List files in directory"""
        start_time = datetime.utcnow()

        try:
            session = await self._get_session()

            url = f"{self.config.base_url}/repos/{owner}/{repo}/contents/{path}"
            params = {"ref": ref}

            async with session.get(url, params=params) as response:
                if response.status == 200:
                    data = await response.json()

                    execution_time = (datetime.utcnow() - start_time).total_seconds()

                    # Handle both file and directory responses
                    items = data if isinstance(data, list) else [data]

                    files = [
                        {
                            "name": item.get("name"),
                            "path": item.get("path"),
                            "type": item.get("type"),
                            "size": item.get("size"),
                            "url": item.get("html_url"),
                        }
                        for item in items
                    ]

                    return GitHubResult(
                        success=True,
                        data={"files": files},
                        execution_time=execution_time,
                    )
                elif response.status == 404:
                    execution_time = (datetime.utcnow() - start_time).total_seconds()
                    return GitHubResult(
                        success=False,
                        error=f"Directory not found: {path}",
                        execution_time=execution_time,
                    )
                else:
                    error_text = await response.text()
                    execution_time = (datetime.utcnow() - start_time).total_seconds()
                    return GitHubResult(
                        success=False,
                        error=f"GitHub API error: {response.status} - {error_text}",
                        execution_time=execution_time,
                    )

        except Exception as e:
            execution_time = (datetime.utcnow() - start_time).total_seconds()
            return GitHubResult(
                success=False,
                error=str(e),
                execution_time=execution_time,
            )

    async def get_repo_info(self, owner: str, repo: str) -> GitHubResult:
        """Get repository information"""
        start_time = datetime.utcnow()

        try:
            session = await self._get_session()

            url = f"{self.config.base_url}/repos/{owner}/{repo}"

            async with session.get(url) as response:
                if response.status == 200:
                    data = await response.json()

                    execution_time = (datetime.utcnow() - start_time).total_seconds()

                    return GitHubResult(
                        success=True,
                        data={
                            "name": data.get("full_name"),
                            "description": data.get("description"),
                            "stars": data.get("stargazers_count"),
                            "forks": data.get("forks_count"),
                            "language": data.get("language"),
                            "default_branch": data.get("default_branch"),
                            "topics": data.get("topics", []),
                            "license": data.get("license", {}).get("name"),
                            "created_at": data.get("created_at"),
                            "updated_at": data.get("updated_at"),
                            "html_url": data.get("html_url"),
                        },
                        execution_time=execution_time,
                    )
                else:
                    error_text = await response.text()
                    execution_time = (datetime.utcnow() - start_time).total_seconds()
                    return GitHubResult(
                        success=False,
                        error=f"GitHub API error: {response.status} - {error_text}",
                        execution_time=execution_time,
                    )

        except Exception as e:
            execution_time = (datetime.utcnow() - start_time).total_seconds()
            return GitHubResult(
                success=False,
                error=str(e),
                execution_time=execution_time,
            )
