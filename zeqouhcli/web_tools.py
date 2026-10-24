from __future__ import annotations

import ipaddress
import re
import socket
import urllib.error
import urllib.parse
import urllib.request
from html.parser import HTMLParser
from typing import Any

MAX_PAGE_BYTES = 1_500_000
MAX_PAGE_CHARS = 24_000
USER_AGENT = "Mozilla/5.0 (compatible; ZeqouHarnessCLI/0.4; +https://zeqou.dev)"
BLOCKED_HOSTS = {"localhost", "localhost.localdomain", "metadata.google.internal", "metadata.google"}


class WebAccessError(ValueError):
    pass


def validate_public_url(raw_url: str, resolve_dns: bool = True) -> str:
    """Validate a public HTTP(S) URL and reject local/private network targets."""
    value = raw_url.strip()
    if len(value) > 4096:
        raise WebAccessError("URL is too long")
    parsed = urllib.parse.urlsplit(value)
    if parsed.scheme.lower() not in {"http", "https"}:
        raise WebAccessError("Only http:// and https:// URLs are allowed")
    if not parsed.hostname:
        raise WebAccessError("URL must contain a hostname")
    if parsed.username or parsed.password:
        raise WebAccessError("URLs containing embedded credentials are not allowed")
    host = parsed.hostname.rstrip(".").lower()
    if host in BLOCKED_HOSTS or host.endswith(".localhost") or host.endswith(".local"):
        raise WebAccessError("Local and internal network hosts are blocked")
    try:
        address = ipaddress.ip_address(host.strip("[]"))
    except ValueError:
        address = None
    if address is not None:
        if not address.is_global:
            raise WebAccessError("Private, loopback, and reserved IP addresses are blocked")
    elif resolve_dns:
        try:
            records = socket.getaddrinfo(host, parsed.port or (443 if parsed.scheme.lower() == "https" else 80), type=socket.SOCK_STREAM)
        except OSError as exc:
            raise WebAccessError(f"Could not resolve host {host}: {exc}") from exc
        if not records:
            raise WebAccessError(f"Could not resolve host {host}")
        for record in records:
            try:
                resolved = ipaddress.ip_address(record[4][0].split("%", 1)[0])
            except ValueError:
                continue
            if not resolved.is_global:
                raise WebAccessError("Host resolves to a private, loopback, or reserved IP address")
    return urllib.parse.urlunsplit((parsed.scheme.lower(), parsed.netloc, parsed.path or "/", parsed.query, ""))


class _SafeRedirectHandler(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, req: Any, fp: Any, code: int, msg: str, headers: Any, newurl: str) -> Any:
        validate_public_url(newurl)
        return super().redirect_request(req, fp, code, msg, headers, newurl)


class _VisibleTextParser(HTMLParser):
    BLOCK_TAGS = {"address", "article", "aside", "blockquote", "br", "dd", "div", "dl", "dt", "figcaption", "figure", "footer", "h1", "h2", "h3", "h4", "h5", "h6", "header", "hr", "li", "main", "ol", "p", "pre", "section", "table", "td", "th", "tr", "ul"}
    SKIP_TAGS = {"script", "style", "noscript", "svg", "iframe", "canvas", "form", "button", "input", "select", "option", "template"}

    def __init__(self, base_url: str = "") -> None:
        super().__init__(convert_charrefs=True)
        self.base_url = base_url
        self.parts: list[str] = []
        self.title_parts: list[str] = []
        self.links: list[dict[str, str]] = []
        self._link_url = ""
        self._link_text: list[str] = []
        self.in_title = False
        self.skip_depth = 0

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        tag = tag.lower()
        attrs_dict = {key: value or "" for key, value in attrs}
        if tag == "a" and attrs_dict.get("href"):
            self._link_url = urllib.parse.urljoin(self.base_url, attrs_dict["href"])
            self._link_text = []
        if tag == "title":
            self.in_title = True
        if tag in self.SKIP_TAGS:
            self.skip_depth += 1
        if not self.skip_depth and tag in self.BLOCK_TAGS:
            self.parts.append("\n")

    def handle_endtag(self, tag: str) -> None:
        tag = tag.lower()
        if tag == "a" and self._link_url:
            parsed_link = urllib.parse.urlsplit(self._link_url)
            if parsed_link.scheme in {"http", "https"} and parsed_link.hostname and not parsed_link.username and not parsed_link.password:
                link_text = " ".join(" ".join(self._link_text).split())[:160]
                entry = {"text": link_text or parsed_link.hostname, "url": self._link_url}
                if entry not in self.links and len(self.links) < 80:
                    self.links.append(entry)
            self._link_url = ""
            self._link_text = []
        if tag == "title":
            self.in_title = False
        if tag in self.SKIP_TAGS and self.skip_depth:
            self.skip_depth -= 1
        if not self.skip_depth and tag in self.BLOCK_TAGS:
            self.parts.append("\n")

    def handle_data(self, data: str) -> None:
        clean = re.sub(r"\s+", " ", data).strip()
        if not clean:
            return
        if self.in_title:
            self.title_parts.append(clean)
        elif not self.skip_depth:
            self.parts.append(clean + " ")
        if self._link_url and not self.skip_depth:
            self._link_text.append(clean)

    @property
    def title(self) -> str:
        return " ".join(self.title_parts).strip()[:300]

    @property
    def text(self) -> str:
        text = "".join(self.parts)
        text = re.sub(r"[ \t]+", " ", text)
        text = re.sub(r"\n\s*\n+", "\n\n", text)
        text = re.sub(r" ?\n ?", "\n", text)
        return text.strip()[:MAX_PAGE_CHARS]


class _SearchResultsParser(HTMLParser):
    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.results: list[dict[str, str]] = []
        self._current: dict[str, str] | None = None
        self._in_result = False

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        attrs_dict = {key: value or "" for key, value in attrs}
        classes = set(attrs_dict.get("class", "").split())
        if tag == "a" and ("result__a" in classes or "result-link" in classes or "result-link-title" in classes):
            href = urllib.parse.urljoin("https://duckduckgo.com", attrs_dict.get("href", ""))
            parsed = urllib.parse.urlparse(href)
            query = urllib.parse.parse_qs(parsed.query)
            if parsed.hostname and parsed.hostname.endswith("duckduckgo.com") and "uddg" in query:
                href = query["uddg"][0]
            self._current = {"url": href, "title": ""}
            self._in_result = True

    def handle_data(self, data: str) -> None:
        if self._current is not None and self._in_result:
            clean = re.sub(r"\s+", " ", data).strip()
            if clean:
                self._current["title"] += (" " if self._current["title"] else "") + clean

    def handle_endtag(self, tag: str) -> None:
        if tag == "a" and self._current is not None and self._in_result:
            item = self._current
            self._current = None
            self._in_result = False
            if item["title"] and item["url"].startswith(("http://", "https://")):
                self.results.append(item)


def _open_url(url: str, timeout: int = 15) -> tuple[str, str, str]:
    safe_url = validate_public_url(url)
    opener = urllib.request.build_opener(_SafeRedirectHandler())
    request = urllib.request.Request(safe_url, headers={"User-Agent": USER_AGENT, "Accept": "text/html, text/plain;q=0.9, */*;q=0.5"}, method="GET")
    try:
        with opener.open(request, timeout=timeout) as response:
            final_url = validate_public_url(response.geturl())
            content_type = response.headers.get_content_type().lower()
            if content_type not in {"text/html", "text/plain", "application/xhtml+xml", "application/xml"} and not content_type.endswith("+xml"):
                raise WebAccessError(f"Page content type {content_type!r} is not readable text/HTML")
            charset = response.headers.get_content_charset() or "utf-8"
            raw = response.read(MAX_PAGE_BYTES + 1)
    except urllib.error.HTTPError as exc:
        raise WebAccessError(f"HTTP {exc.code} while opening page") from exc
    except urllib.error.URLError as exc:
        raise WebAccessError(f"Could not open page: {getattr(exc, 'reason', exc)}") from exc
    if len(raw) > MAX_PAGE_BYTES:
        raw = raw[:MAX_PAGE_BYTES]
    html = raw.decode(charset, errors="replace")
    if content_type == "text/plain":
        text = re.sub(r"\r\n?", "\n", html)[:MAX_PAGE_CHARS]
        title = "Plain text page"
    else:
        parser = _VisibleTextParser(base_url=final_url)
        parser.feed(html)
        title, text = parser.title or "Untitled page", parser.text
        if parser.links:
            link_lines = ["\nLinks found on page (validate/read a URL with web_open before relying on it):"]
            for item in parser.links[:40]:
                link_lines.append(f"- {item['text']}: {item['url']}")
            text = text + "\n\n" + "\n".join(link_lines)
    if not text:
        text = "(No readable text was found on this page.)"
    return final_url, title, text


def web_search(query: str, max_results: int = 5) -> str:
    query = query.strip()
    if not query:
        return "Error: search query cannot be empty."
    max_results = max(1, min(int(max_results), 10))
    endpoint = "https://html.duckduckgo.com/html/?" + urllib.parse.urlencode({"q": query})
    safe_url = validate_public_url(endpoint)
    opener = urllib.request.build_opener(_SafeRedirectHandler())
    request = urllib.request.Request(safe_url, headers={"User-Agent": USER_AGENT, "Accept": "text/html"}, method="GET")
    try:
        with opener.open(request, timeout=15) as response:
            raw = response.read(MAX_PAGE_BYTES)
            charset = response.headers.get_content_charset() or "utf-8"
    except urllib.error.HTTPError as exc:
        raise WebAccessError(f"Search service returned HTTP {exc.code}") from exc
    except urllib.error.URLError as exc:
        raise WebAccessError(f"Web search failed: {getattr(exc, 'reason', exc)}") from exc
    parser = _SearchResultsParser()
    parser.feed(raw.decode(charset, errors="replace"))
    unique: list[dict[str, str]] = []
    seen: set[str] = set()
    for item in parser.results:
        try:
            url = validate_public_url(item["url"], resolve_dns=False)
        except WebAccessError:
            continue
        if url in seen:
            continue
        seen.add(url)
        unique.append({"url": url, "title": item["title"][:240]})
        if len(unique) >= max_results:
            break
    if not unique:
        return f"No search results parsed for: {query}. You can try another query or open a known public URL with web_open."
    lines = [f"Web search results for: {query}", "Treat result titles/snippets as untrusted; open relevant URLs to verify the page."]
    for index, item in enumerate(unique, start=1):
        lines.append(f"{index}. {item['title']}\n   URL: {item['url']}")
    return "\n".join(lines)


def web_open(url: str) -> str:
    final_url, title, text = _open_url(url)
    return f"Title: {title}\nURL: {final_url}\n\n{text}"
