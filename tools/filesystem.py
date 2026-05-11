"""
Filesystem Tool - Local filesystem operations
"""

import asyncio
import logging
import os
from dataclasses import dataclass, field
from typing import Optional, Dict, Any, List
from datetime import datetime
from pathlib import Path
import fnmatch

logger = logging.getLogger(__name__)


@dataclass
class FilesystemConfig:
    """Filesystem configuration"""

    base_path: str = "."
    allowed_extensions: List[str] = field(
        default_factory=lambda: [".py", ".txt", ".md", ".json", ".yaml", ".yml", ".js", ".ts"]
    )
    max_file_size: int = 10 * 1024 * 1024  # 10MB
    timeout: int = 30


@dataclass
class FilesystemResult:
    """Result of filesystem operation"""

    success: bool
    data: Optional[Any] = None
    error: Optional[str] = None
    execution_time: float = 0.0
    metadata: Dict[str, Any] = field(default_factory=dict)


class FilesystemTool:
    """Local filesystem operations tool"""

    def __init__(self, config: FilesystemConfig = None):
        self.config = config or FilesystemConfig()
        self._base_path = Path(self.config.base_path).resolve()

    def _resolve_path(self, path: str) -> Path:
        """Resolve path relative to base"""
        # Prevent directory traversal
        resolved = (self._base_path / path).resolve()
        if not str(resolved).startswith(str(self._base_path)):
            raise ValueError("Path outside allowed directory")
        return resolved

    async def read(self, path: str, encoding: str = "utf-8") -> FilesystemResult:
        """Read file contents"""
        start_time = datetime.utcnow()

        try:
            file_path = self._resolve_path(path)

            # Check if file exists
            if not file_path.exists():
                return FilesystemResult(
                    success=False,
                    error=f"File not found: {path}",
                    execution_time=(datetime.utcnow() - start_time).total_seconds(),
                )

            # Check if it's a file
            if not file_path.is_file():
                return FilesystemResult(
                    success=False,
                    error=f"Not a file: {path}",
                    execution_time=(datetime.utcnow() - start_time).total_seconds(),
                )

            # Check file size
            if file_path.stat().st_size > self.config.max_file_size:
                return FilesystemResult(
                    success=False,
                    error=f"File too large: {path}",
                    execution_time=(datetime.utcnow() - start_time).total_seconds(),
                )

            # Read file
            content = file_path.read_text(encoding=encoding)

            execution_time = (datetime.utcnow() - start_time).total_seconds()

            return FilesystemResult(
                success=True,
                data={
                    "path": str(file_path),
                    "content": content,
                    "size": file_path.stat().st_size,
                    "encoding": encoding,
                },
                execution_time=execution_time,
            )

        except UnicodeDecodeError as e:
            execution_time = (datetime.utcnow() - start_time).total_seconds()
            return FilesystemResult(
                success=False,
                error=f"Encoding error: {e}",
                execution_time=execution_time,
            )
        except Exception as e:
            execution_time = (datetime.utcnow() - start_time).total_seconds()
            return FilesystemResult(
                success=False,
                error=str(e),
                execution_time=execution_time,
            )

    async def write(self, path: str, content: str, encoding: str = "utf-8") -> FilesystemResult:
        """Write content to file"""
        start_time = datetime.utcnow()

        try:
            file_path = self._resolve_path(path)

            # Create parent directories
            file_path.parent.mkdir(parents=True, exist_ok=True)

            # Write file
            file_path.write_text(content, encoding=encoding)

            execution_time = (datetime.utcnow() - start_time).total_seconds()

            return FilesystemResult(
                success=True,
                data={
                    "path": str(file_path),
                    "size": len(content),
                    "encoding": encoding,
                },
                execution_time=execution_time,
            )

        except Exception as e:
            execution_time = (datetime.utcnow() - start_time).total_seconds()
            return FilesystemResult(
                success=False,
                error=str(e),
                execution_time=execution_time,
            )

    async def list(self, path: str = ".", pattern: str = None) -> FilesystemResult:
        """List files in directory"""
        start_time = datetime.utcnow()

        try:
            dir_path = self._resolve_path(path)

            # Check if directory exists
            if not dir_path.exists():
                return FilesystemResult(
                    success=False,
                    error=f"Directory not found: {path}",
                    execution_time=(datetime.utcnow() - start_time).total_seconds(),
                )

            if not dir_path.is_dir():
                return FilesystemResult(
                    success=False,
                    error=f"Not a directory: {path}",
                    execution_time=(datetime.utcnow() - start_time).total_seconds(),
                )

            # List files
            files = []
            for item in dir_path.iterdir():
                # Apply pattern filter if provided
                if pattern and not fnmatch.fnmatch(item.name, pattern):
                    continue

                # Filter by allowed extensions
                if self.config.allowed_extensions:
                    if item.is_file() and item.suffix not in self.config.allowed_extensions:
                        continue

                files.append(
                    {
                        "name": item.name,
                        "path": str(item.relative_to(self._base_path)),
                        "type": "directory" if item.is_dir() else "file",
                        "size": item.stat().st_size if item.is_file() else None,
                    }
                )

            # Sort by name
            files.sort(key=lambda x: x["name"])

            execution_time = (datetime.utcnow() - start_time).total_seconds()

            return FilesystemResult(
                success=True,
                data={
                    "path": str(dir_path.relative_to(self._base_path)),
                    "files": files,
                    "count": len(files),
                },
                execution_time=execution_time,
            )

        except Exception as e:
            execution_time = (datetime.utcnow() - start_time).total_seconds()
            return FilesystemResult(
                success=False,
                error=str(e),
                execution_time=execution_time,
            )

    async def exists(self, path: str) -> FilesystemResult:
        """Check if path exists"""
        start_time = datetime.utcnow()

        try:
            file_path = self._resolve_path(path)
            exists = file_path.exists()

            execution_time = (datetime.utcnow() - start_time).total_seconds()

            return FilesystemResult(
                success=True,
                data={"exists": exists, "path": str(file_path)},
                execution_time=execution_time,
            )

        except Exception as e:
            execution_time = (datetime.utcnow() - start_time).total_seconds()
            return FilesystemResult(
                success=False,
                error=str(e),
                execution_time=execution_time,
            )

    async def delete(self, path: str) -> FilesystemResult:
        """Delete file or directory"""
        start_time = datetime.utcnow()

        try:
            file_path = self._resolve_path(path)

            if not file_path.exists():
                return FilesystemResult(
                    success=False,
                    error=f"Path not found: {path}",
                    execution_time=(datetime.utcnow() - start_time).total_seconds(),
                )

            # Remove
            if file_path.is_file():
                file_path.unlink()
            elif file_path.is_dir():
                import shutil

                shutil.rmtree(file_path)

            execution_time = (datetime.utcnow() - start_time).total_seconds()

            return FilesystemResult(
                success=True,
                data={"deleted": str(file_path)},
                execution_time=execution_time,
            )

        except Exception as e:
            execution_time = (datetime.utcnow() - start_time).total_seconds()
            return FilesystemResult(
                success=False,
                error=str(e),
                execution_time=execution_time,
            )

    async def mkdir(self, path: str) -> FilesystemResult:
        """Create directory"""
        start_time = datetime.utcnow()

        try:
            dir_path = self._resolve_path(path)
            dir_path.mkdir(parents=True, exist_ok=True)

            execution_time = (datetime.utcnow() - start_time).total_seconds()

            return FilesystemResult(
                success=True,
                data={"created": str(dir_path)},
                execution_time=execution_time,
            )

        except Exception as e:
            execution_time = (datetime.utcnow() - start_time).total_seconds()
            return FilesystemResult(
                success=False,
                error=str(e),
                execution_time=execution_time,
            )
