# server.py
import sys
import logging
import json
from datetime import datetime
import time
import math
import random
import requests
from bs4 import BeautifulSoup
from concurrent.futures import ThreadPoolExecutor
from typing import List, Dict, Optional, Any, Set

# MCP server (giữ nguyên nếu bạn đã có package)
from mcp.server.fastmcp import FastMCP

logger = logging.getLogger('log')
logger.setLevel(logging.INFO)
handler = logging.StreamHandler(sys.stdout)
handler.setFormatter(logging.Formatter('%(asctime)s %(levelname)s %(message)s'))
logger.addHandler(handler)

# Fix UTF-8 encoding for Windows console
if sys.platform == 'win32':
    try:
        sys.stderr.reconfigure(encoding='utf-8')
        sys.stdout.reconfigure(encoding='utf-8')
    except Exception:
        pass


# --- Utility functions ---
def load_config() -> Dict[str, Any]:
    try:
        with open('config.json', 'r', encoding='utf-8') as f:
            return json.load(f)
    except FileNotFoundError:
        logger.warning("config.json không tồn tại — sử dụng cấu hình mặc định rỗng.")
        return {}
    except Exception as e:
        logger.exception("Lỗi đọc config.json: %s", e)
        return {}


def save_log(message: str) -> None:
    try:
        with open('query.log', 'a', encoding='utf-8') as f:
            f.write(f"{datetime.now().isoformat()} - {message}\n")
    except Exception:
        logger.exception("Không ghi được log vào file.")


def fetch_page_meta(url: str, timeout: int = 6) -> Dict[str, Optional[str]]:
    """Lấy title và meta description từ 1 URL."""
    try:
        headers = {
            "User-Agent": "Mozilla/5.0 (compatible; MultiSourceBot/1.0; +https://example.local/)",
            "Accept-Language": "en-US,en;q=0.9"
        }
        resp = requests.get(url, headers=headers, timeout=timeout)
        resp.raise_for_status()
        soup = BeautifulSoup(resp.text, "html.parser")
        title_tag = soup.find("title")
        title = title_tag.get_text(strip=True) if title_tag else None
        desc_tag = soup.find("meta", attrs={"name": "description"}) or soup.find(
            "meta", attrs={"property": "og:description"})
        description = desc_tag["content"].strip() if (desc_tag and desc_tag.get("content")) else None
        return {"title": title, "description": description}
    except Exception:
        return {"title": None, "description": None}


# --- Search adapters ---
class MultiSourceSearcher:
    def __init__(self, config: Dict[str, Any]):
        self.config = config

    # ---- SerpAPI ----
    def search_serpapi(self, q: str, count: int = 10) -> List[Dict]:
        results = []
        api_key = self.config.get("SERPAPI_KEY")
        if not api_key:
            return results
        try:
            params = {"engine": "google", "q": q, "api_key": api_key, "num": min(count, 100)}
            resp = requests.get("https://serpapi.com/search.json", params=params, timeout=8)
            resp.raise_for_status()
            data = resp.json()
            organic = data.get("organic_results", []) or data.get("organic", [])
            for o in organic:
                results.append({
                    "title": o.get("title") or o.get("position"),
                    "url": o.get("link") or o.get("url"),
                    "snippet": o.get("snippet") or None,
                    "source": "serpapi"
                })
        except Exception:
            logger.exception("SerpAPI search error")
        return results

    # ---- Serper (Google-like API) ----
    def search_serper(self, q: str, count: int = 10) -> List[Dict]:
        results = []
        api_key = self.config.get("SERPER_API_KEY")
        if not api_key:
            return results
        try:
            headers = {"X-API-KEY": api_key, "Content-Type": "application/json"}
            payload = {"q": q, "num": min(count, 20)}
            resp = requests.post("https://google.serper.dev/search", json=payload, headers=headers, timeout=8)
            resp.raise_for_status()
            data = resp.json()
            for item in data.get("organic", [])[:count]:
                results.append({
                    "title": item.get("title"),
                    "url": item.get("link"),
                    "snippet": item.get("snippet"),
                    "source": "serper"
                })
        except Exception:
            logger.exception("Serper search error")
        return results

    # ---- DuckDuckGo HTML ----
    def search_duckduckgo(self, q: str, count: int = 10) -> List[Dict]:
        results = []
        try:
            params = {"q": q}
            resp = requests.post("https://html.duckduckgo.com/html/",
                                 data=params, timeout=8,
                                 headers={"User-Agent": "Mozilla/5.0"})
            resp.raise_for_status()
            soup = BeautifulSoup(resp.text, "html.parser")
            links = soup.select("a.result__a") or soup.select("a.result-link")
            for a in links[:count]:
                href = a.get("href")
                title = a.get_text(strip=True)
                results.append({"title": title, "url": href, "snippet": None, "source": "duckduckgo"})
        except Exception:
            logger.exception("DuckDuckGo search error")
        return results


# --- MCP server setup ---
mcp = FastMCP("mcps")
searcher = MultiSourceSearcher(load_config())


# --- Tool definition ---
@mcp.tool()
def tra_cuu_qua_mang(query_text: str,
                     count: int = 15,
                     sources: Optional[List[str]] = None,
                     domain_filter: Optional[str] = None) -> Dict[str, Any]:
    """Tra cứu trên nhiều nguồn (Bing, SerpAPI, Serper, DuckDuckGo)."""
    config = load_config()
    start_ts = time.time()
    save_log(f"QUERY: {query_text}")

    # Tự động xác định nguồn có key
    default_sources = []
    if config.get("SERPAPI_KEY"):
        default_sources.append("serpapi")
    if config.get("SERPER_API_KEY"):
        default_sources.append("serper")
    default_sources.append("duckduckgo")

    chosen = sources or default_sources
    chosen = [s.lower() for s in chosen]

    # Map nguồn
    source_funcs = {
        "serpapi": lambda q, n: searcher.search_serpapi(q, n),
        "serper": lambda q, n: searcher.search_serper(q, n),
        "duckduckgo": lambda q, n: searcher.search_duckduckgo(q, n),
    }

    n_sources = max(1, len(chosen))
    per_source = max(1, math.ceil(count / n_sources))
    results: List[Dict[str, Any]] = []
    seen_urls: Set[str] = set()

    with ThreadPoolExecutor(max_workers=min(8, n_sources)) as exe:
        futures = {exe.submit(source_funcs[src], query_text, per_source): src for src in chosen if src in source_funcs}

        from concurrent.futures import wait, ALL_COMPLETED
        done, not_done = wait(list(futures.keys()), timeout=20, return_when=ALL_COMPLETED)

        for f in not_done:
            f.cancel()

        for f in done:
            src = futures[f]
            try:
                items = f.result()
            except Exception as e:
                logger.exception("Lỗi khi chạy nguồn %s: %s", src, e)
                items = []

            for it in items:
                url = it.get("url")
                if not url or url in seen_urls:
                    continue
                seen_urls.add(url)
                if not it.get("snippet") or not it.get("title"):
                    meta = fetch_page_meta(url)
                    it["title"] = it.get("title") or meta.get("title")
                    it["snippet"] = it.get("snippet") or meta.get("description")
                results.append({
                    "title": it.get("title") or "",
                    "url": url.split("?")[0],
                    "snippet": it.get("snippet") or "",
                    "source": it.get("source") or src
                })
                if len(results) >= count:
                    break
            if len(results) >= count:
                break

    elapsed = time.time() - start_ts
    logger.info("Tra cứu xong: %d kết quả trong %.2fs (nguồn: %s)", len(results), elapsed, ", ".join(chosen))
    save_log(f"RESULT_COUNT: {len(results)} for query: {query_text} in {elapsed:.2f}s")

    return {
        "success": True,
        "query": query_text,
        "took_seconds": round(elapsed, 2),
        "result_count": len(results),
        "result": results
    }


# --- Start server ---
if __name__ == "__main__":
    mcp.run(transport="stdio")
