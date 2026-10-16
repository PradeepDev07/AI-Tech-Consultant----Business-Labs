"""Sitemap discovery, safe XML parsing, and URL normalization."""

from dataclasses import dataclass
from datetime import datetime
from typing import Sequence
import urllib.parse
import xml.etree.ElementTree as ET
import httpx
from app.core.exceptions import IngestionError
from app.core.logging import logger

SITEMAP_NS = "{http://www.sitemaps.org/schemas/sitemap/0.9}"
STRIPPED_QUERY_PARAMS = {
    "utm_source",
    "utm_medium",
    "utm_campaign",
    "utm_term",
    "utm_content",
    "ref",
    "fbclid",
    "gclid",
    "_ga",
}


@dataclass
class DiscoveredUrl:
    """Discovered URL entry from sitemap."""

    url: str
    lastmod: str | None = None
    changefreq: str | None = None
    priority: float | None = None


def normalize_url(raw_url: str) -> str:
    """Normalize URL by removing fragments, sorting/filtering tracking query params, and normalizing casing."""
    parsed = urllib.parse.urlsplit(raw_url.strip())
    scheme = parsed.scheme.lower()
    netloc = parsed.netloc.lower()

    # Normalize path (remove redundant trailing slash unless it's root)
    path = parsed.path
    if path != "/" and path.endswith("/"):
        path = path.rstrip("/")

    # Filter out analytics and tracking parameters
    query_params = urllib.parse.parse_qsl(parsed.query, keep_blank_values=False)
    filtered_params = [
        (k, v) for k, v in query_params if k.lower() not in STRIPPED_QUERY_PARAMS
    ]
    filtered_params.sort(key=lambda x: x[0])
    new_query = urllib.parse.urlencode(filtered_params)

    # Reconstruct URL without fragment
    return urllib.parse.urlunsplit((scheme, netloc, path, new_query, ""))


def is_url_in_allowed_domain(url: str, allowed_host: str) -> bool:
    """Verify that the URL host matches the allowed host."""
    parsed = urllib.parse.urlsplit(url)
    return parsed.netloc.lower() == allowed_host.lower()


class SitemapParser:
    """Parser for sitemap XML and sitemap index files."""

    def __init__(
        self,
        allowed_host: str = "support.brilliantdirectories.com",
        timeout_seconds: float = 15.0,
        user_agent: str = "KnowledgeBrainBot/1.0",
    ):
        self.allowed_host = allowed_host
        self.timeout_seconds = timeout_seconds
        self.user_agent = user_agent

    def parse_xml_content(
        self, xml_text: str
    ) -> tuple[list[DiscoveredUrl], list[str]]:
        """Safely parse XML content into list of DiscoveredUrls or child sitemap URLs.

        Returns (discovered_urls, sub_sitemap_urls).
        """
        try:
            root = ET.fromstring(xml_text)
        except ET.ParseError as e:
            raise IngestionError(f"Failed to parse sitemap XML: {e}") from e

        tag = root.tag
        if tag.startswith("{"):
            tag = tag.split("}", 1)[1]

        # Handle Sitemap Index
        if tag == "sitemapindex":
            sub_sitemaps: list[str] = []
            for sm in root.findall(f".//{SITEMAP_NS}sitemap"):
                loc_elem = sm.find(f"{SITEMAP_NS}loc")
                if loc_elem is not None and loc_elem.text:
                    sub_url = loc_elem.text.strip()
                    if is_url_in_allowed_domain(sub_url, self.allowed_host):
                        sub_sitemaps.append(sub_url)
            return [], sub_sitemaps

        # Handle Urlset
        discovered: list[DiscoveredUrl] = []
        seen_urls: set[str] = set()

        for url_elem in root.findall(f".//{SITEMAP_NS}url"):
            loc_elem = url_elem.find(f"{SITEMAP_NS}loc")
            if loc_elem is None or not loc_elem.text:
                continue

            raw_url = loc_elem.text.strip()
            norm_url = normalize_url(raw_url)

            if not is_url_in_allowed_domain(norm_url, self.allowed_host):
                logger.debug(f"Ignoring out-of-domain URL: {norm_url}")
                continue

            if norm_url in seen_urls:
                continue
            seen_urls.add(norm_url)

            lastmod_elem = url_elem.find(f"{SITEMAP_NS}lastmod")
            lastmod = lastmod_elem.text.strip() if lastmod_elem is not None and lastmod_elem.text else None

            changefreq_elem = url_elem.find(f"{SITEMAP_NS}changefreq")
            changefreq = (
                changefreq_elem.text.strip()
                if changefreq_elem is not None and changefreq_elem.text
                else None
            )

            priority_elem = url_elem.find(f"{SITEMAP_NS}priority")
            priority = None
            if priority_elem is not None and priority_elem.text:
                try:
                    priority = float(priority_elem.text.strip())
                except ValueError:
                    priority = None

            discovered.append(
                DiscoveredUrl(
                    url=norm_url,
                    lastmod=lastmod,
                    changefreq=changefreq,
                    priority=priority,
                )
            )

        return discovered, []

    async def fetch_and_discover(
        self, sitemap_url: str, client: httpx.AsyncClient | None = None
    ) -> list[DiscoveredUrl]:
        """Recursively fetch sitemap and any linked child sitemaps."""
        headers = {"User-Agent": self.user_agent}
        close_client = False
        if client is None:
            client = httpx.AsyncClient(timeout=self.timeout_seconds, headers=headers)
            close_client = True

        try:
            logger.info(f"Fetching sitemap from: {sitemap_url}")
            response = await client.get(sitemap_url)
            response.raise_for_status()

            urls, sub_sitemaps = self.parse_xml_content(response.text)
            if not sub_sitemaps:
                return urls

            all_urls: list[DiscoveredUrl] = list(urls)
            for sub_url in sub_sitemaps:
                sub_discovered = await self.fetch_and_discover(sub_url, client=client)
                all_urls.extend(sub_discovered)

            # Deduplicate across sitemaps
            unique_urls: dict[str, DiscoveredUrl] = {}
            for item in all_urls:
                if item.url not in unique_urls:
                    unique_urls[item.url] = item
            return list(unique_urls.values())

        except httpx.HTTPError as e:
            raise IngestionError(f"HTTP error fetching sitemap {sitemap_url}: {e}") from e
        finally:
            if close_client:
                await client.aclose()
