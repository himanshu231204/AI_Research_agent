"""
Citation Verification System for Research OS.

Provides:
- Source validation
- Duplicate detection
- Broken citation detection
- Hallucinated citation detection
"""

import logging
import re
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Any, Dict, List, Optional, Set

import httpx

logger = logging.getLogger(__name__)


class CitationIssueType(Enum):
    """Types of citation issues."""

    VALID = "valid"
    MISSING = "missing"
    BROKEN = "broken"
    HALLUCINATED = "hallucinated"
    UNSUPPORTED = "unsupported"
    CREDIBILITY_LOW = "credibility_low"
    FORMAT_INVALID = "format_invalid"
    DUPLICATE = "duplicate"


class SourceCredibility(Enum):
    """Source credibility levels."""

    HIGH = "high"  # Peer-reviewed, official sources
    MEDIUM = "medium"  # Established websites
    LOW = "low"  # Unknown sources
    UNKNOWN = "unknown"


@dataclass
class Citation:
    """Represents a single citation/reference."""

    raw: str
    url: Optional[str] = None
    title: Optional[str] = None
    authors: List[str] = field(default_factory=list)
    publication_date: Optional[str] = None
    source: Optional[str] = None
    credibility: str = "unknown"

    def to_dict(self) -> Dict[str, Any]:
        return {
            "raw": self.raw,
            "url": self.url,
            "title": self.title,
            "authors": self.authors,
            "publication_date": self.publication_date,
            "source": self.source,
            "credibility": self.credibility,
        }


@dataclass
class CitationIssue:
    """Represents an issue with a citation."""

    citation: str
    issue_type: CitationIssueType
    severity: str  # high | medium | low
    description: str
    affected_claims: List[str] = field(default_factory=list)
    suggestion: Optional[str] = None

    def to_dict(self) -> Dict[str, Any]:
        return {
            "citation": self.citation,
            "issue_type": self.issue_type.value,
            "severity": self.severity,
            "description": self.description,
            "affected_claims": self.affected_claims,
            "suggestion": self.suggestion,
        }


@dataclass
class VerificationResult:
    """Result of citation verification."""

    total_citations: int
    valid_citations: int
    issues: List[CitationIssue]
    credibility_scores: Dict[str, float]
    duplicate_groups: List[List[str]]
    verified_at: datetime

    @property
    def is_verified(self) -> bool:
        """Check if all citations are valid."""
        return self.valid_citations == self.total_citations and not any(
            i.severity == "high" for i in self.issues
        )

    @property
    def overall_credibility(self) -> float:
        """Calculate overall credibility score."""
        if not self.credibility_scores:
            return 0.0
        return sum(self.credibility_scores.values()) / len(self.credibility_scores)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "total_citations": self.total_citations,
            "valid_citations": self.valid_citations,
            "issues": [i.to_dict() for i in self.issues],
            "credibility_scores": self.credibility_scores,
            "duplicate_groups": self.duplicate_groups,
            "is_verified": self.is_verified,
            "overall_credibility": self.overall_credibility,
            "verified_at": self.verified_at.isoformat(),
        }


class CitationParser:
    """Parse and extract citations from text."""

    # Common citation patterns
    URL_PATTERN = r"https?://[^\s\)\]\}\"']+"
    MARKDOWN_LINK_PATTERN = r"\[([^\]]+)\]\(([^\)]+)\)"
    NUMBERED_REF_PATTERN = r"\[\d+\]"
    AUTHOR_DATE_PATTERN = r"\([A-Z][a-z]+(?:\s+et\s+al\.?)?,?\s+\d{4}\)"

    def parse_citations(self, text: str) -> List[Citation]:
        """
        Extract all citations from text.

        Args:
            text: Text containing citations

        Returns:
            List of Citation objects
        """
        citations = []

        # Extract URLs
        urls = re.findall(self.URL_PATTERN, text)
        for url in urls:
            citations.append(
                Citation(
                    raw=url,
                    url=url,
                    source=self._extract_domain(url),
                )
            )

        # Extract markdown links
        markdown_links = re.findall(self.MARKDOWN_LINK_PATTERN, text)
        for title, url in markdown_links:
            citations.append(
                Citation(
                    raw=f"[{title}]({url})",
                    url=url,
                    title=title,
                    source=self._extract_domain(url),
                )
            )

        # Extract author-date references
        author_dates = re.findall(self.AUTHOR_DATE_PATTERN, text)
        for ref in author_dates:
            citations.append(
                Citation(
                    raw=ref,
                    publication_date=self._extract_year(ref),
                )
            )

        return citations

    def _extract_domain(self, url: str) -> Optional[str]:
        """Extract domain from URL."""
        match = re.search(r"https?://([^/]+)", url)
        return match.group(1) if match else None

    def _extract_year(self, text: str) -> Optional[str]:
        """Extract year from text."""
        match = re.search(r"\d{4}", text)
        return match.group(0) if match else None


class CitationVerifier:
    """
    Verify citations for validity and credibility.

    Checks:
    - Source credibility
    - URL validity
    - Duplicate citations
    - Hallucinated citations
    """

    # High credibility domains
    HIGH_CREDIBILITY_DOMAINS = {
        "arxiv.org",
        "nature.com",
        "science.org",
        "nih.gov",
        "cdc.gov",
        "who.int",
        "wikipedia.org",
        "github.com",
        "stackoverflow.com",
        "medium.com",
        "dev.to",
        "substack.com",
    }

    # Low credibility indicators
    LOW_CREDIBILITY_INDICATORS = {
        "blogspot.com",
        "wordpress.com",
        "blogger.com",
        "weebly.com",
        "wix.com",
        "squarespace.com",
    }

    def __init__(self):
        """Initialize citation verifier."""
        self.parser = CitationParser()
        self._verified_urls: Set[str] = set()

    async def verify(
        self,
        citations: List[str],
        claims: Optional[List[str]] = None,
    ) -> VerificationResult:
        """
        Verify a list of citations.

        Args:
            citations: List of citation strings
            claims: Optional list of claims attributed to citations

        Returns:
            VerificationResult
        """
        issues = []
        credibility_scores = {}
        seen_citations: Dict[str, int] = {}
        duplicate_groups = []

        valid_count = 0

        for citation_text in citations:
            citation_issues = []
            citation_issues_severity = "low"

            # Parse citation
            parsed = self.parser.parse_citations(citation_text)

            if not parsed:
                issues.append(
                    CitationIssue(
                        citation=citation_text,
                        issue_type=CitationIssueType.MISSING,
                        severity="high",
                        description="Could not parse citation format",
                    )
                )
                continue

            citation = parsed[0]

            # Check for duplicates
            seen_key = citation.url or citation.raw
            if seen_key in seen_citations:
                duplicate_idx = seen_citations[seen_key]
                if duplicate_idx < len(duplicate_groups):
                    duplicate_groups[duplicate_idx].append(citation_text)
                else:
                    duplicate_groups.append([seen_key, citation_text])
                seen_citations[seen_key] = len(duplicate_groups) - 1
                issues.append(
                    CitationIssue(
                        citation=citation_text,
                        issue_type=CitationIssueType.DUPLICATE,
                        severity="low",
                        description="Duplicate citation detected",
                    )
                )
            else:
                seen_citations[seen_key] = len(duplicate_groups)
                duplicate_groups.append([citation_text])

            # Check URL validity
            if citation.url:
                is_valid, validity_msg = await self._verify_url(citation.url)
                if not is_valid:
                    citation_issues.append(validity_msg)
                    citation_issues_severity = "high"

            # Check credibility
            credibility_score, cred_level = self._assess_credibility(citation)
            citation.credibility = cred_level.value
            credibility_scores[citation_text] = credibility_score

            # Check for hallucination indicators
            if self._is_potentially_hallucinated(citation_text):
                citation_issues.append("Potentially hallucinated citation (non-existent reference)")
                citation_issues_severity = "high"

            # Add issues
            if citation_issues:
                issues.extend(
                    [
                        CitationIssue(
                            citation=citation_text,
                            issue_type=CitationIssueType.UNSUPPORTED
                            if "valid" in issue.lower()
                            else CitationIssueType.CREDIBILITY_LOW,
                            severity=citation_issues_severity,
                            description=issue,
                        )
                        for issue in citation_issues
                    ]
                )
            else:
                valid_count += 1

        return VerificationResult(
            total_citations=len(citations),
            valid_citations=valid_count,
            issues=issues,
            credibility_scores=credibility_scores,
            duplicate_groups=[g for g in duplicate_groups if len(g) > 1],
            verified_at=datetime.utcnow(),
        )

    async def _verify_url(self, url: str) -> tuple[bool, str]:
        """
        Verify URL is accessible.

        Args:
            url: URL to verify

        Returns:
            Tuple of (is_valid, message)
        """
        # Check cache first
        if url in self._verified_urls:
            return True, "Previously verified"

        try:
            async with httpx.AsyncClient(timeout=10.0) as client:
                response = await client.head(url, follow_redirects=True)

                if response.status_code == 200:
                    self._verified_urls.add(url)
                    return True, "URL is valid and accessible"
                elif response.status_code == 404:
                    return False, f"URL returned 404 (Not Found)"
                elif response.status_code >= 500:
                    return False, f"URL returned server error ({response.status_code})"
                else:
                    return True, f"URL exists but returned {response.status_code}"

        except httpx.TimeoutException:
            return True, "URL timeout (assuming valid for now)"
        except httpx.RequestError as e:
            return False, f"URL request failed: {str(e)}"

    def _assess_credibility(self, citation: Citation) -> tuple[float, SourceCredibility]:
        """
        Assess the credibility of a citation.

        Args:
            citation: Citation to assess

        Returns:
            Tuple of (score, credibility level)
        """
        if not citation.source:
            return 0.5, SourceCredibility.UNKNOWN

        source_lower = citation.source.lower()

        # High credibility
        if any(domain in source_lower for domain in self.HIGH_CREDIBILITY_DOMAINS):
            return 0.9, SourceCredibility.HIGH

        # Low credibility indicators
        if any(domain in source_lower for domain in self.LOW_CREDIBILITY_INDICATORS):
            return 0.3, SourceCredibility.LOW

        # Academic/Government domains
        if any(domain in source_lower for domain in [".edu", ".gov", ".ac.uk"]):
            return 0.85, SourceCredibility.HIGH

        # Default medium credibility for known domains
        if "." in source_lower:
            return 0.6, SourceCredibility.MEDIUM

        return 0.5, SourceCredibility.UNKNOWN

    def _is_potentially_hallucinated(self, citation: str) -> bool:
        """
        Check if citation appears to be hallucinated.

        Args:
            citation: Citation string

        Returns:
            True if potentially hallucinated
        """
        # Check for nonsensical patterns
        hallucination_patterns = [
            r"https?://[a-z]\.[a-z]\.[a-z]",  # Very short domains
            r"https?://\d{1,3}\.\d{1,3}\.\d{1,3}",  # IP addresses only
            r"https?://[a-z]{20,}\.[a-z]{2,}",  # Very long random-looking domains
        ]

        for pattern in hallucination_patterns:
            if re.search(pattern, citation, re.IGNORECASE):
                return True

        # Check for citation formats that don't match any pattern
        if not re.search(
            r"(https?://|\[[^\]]+\]|\([A-Z][a-z]+,?\s+\d{4}\))",
            citation,
        ):
            if len(citation) > 50 and not re.search(r"\s", citation):
                return True

        return False


class CitationFormatter:
    """Format citations for reports."""

    @staticmethod
    def format_mla(citation: Citation) -> str:
        """Format citation in MLA style."""
        parts = []

        if citation.authors:
            parts.append(", ".join(citation.authors))

        if citation.title:
            parts.append(f'"{citation.title}"')

        if citation.source:
            parts.append(citation.source)

        if citation.publication_date:
            parts.append(citation.publication_date)

        if citation.url:
            parts.append(citation.url)

        return ", ".join(parts)

    @staticmethod
    def format_apa(citation: Citation) -> str:
        """Format citation in APA style."""
        parts = []

        if citation.authors:
            parts.append(", ".join(citation.authors))

        if citation.publication_date:
            parts.append(f"({citation.publication_date})")

        if citation.title:
            parts.append(citation.title)

        if citation.source:
            parts.append(f"<i>{citation.source}</i>")

        if citation.url:
            parts.append(f"Retrieved from {citation.url}")

        return ". ".join(parts)

    @staticmethod
    def format_hyperlinks(citations: List[Citation]) -> str:
        """Format as Markdown hyperlinks."""
        parts = []

        for i, citation in enumerate(citations, 1):
            if citation.url:
                title = citation.title or citation.url
                parts.append(f"[{i}. {title}]({citation.url})")
            elif citation.raw:
                parts.append(f"[{i}. {citation.raw}]")

        return "\n".join(parts)


# Convenience function
async def verify_citations(
    citations: List[str],
    claims: Optional[List[str]] = None,
) -> VerificationResult:
    """
    Verify citations.

    Args:
        citations: List of citation strings
        claims: Optional claims attributed to citations

    Returns:
        VerificationResult
    """
    verifier = CitationVerifier()
    return await verifier.verify(citations, claims)
