import cloudscraper
from bs4 import BeautifulSoup
import json
import time
import random
import os
from concurrent.futures import ThreadPoolExecutor
import threading
import gc

BASE_URL = "https://www.cubecraft.net"

# Your custom target URLs
TARGET_URLS = [
    "https://www.cubecraft.net/forums/game-discussions.153/",
    "https://www.cubecraft.net/forums/suggestions/",
    "https://www.cubecraft.net/forums/forum-games.57/",
    "https://www.cubecraft.net/forums/introductions.3/",
    "https://www.cubecraft.net/forums/news/",
    "https://www.cubecraft.net/forums/the-lobby.67/",
    "https://www.cubecraft.net/forums/support.70/",
    "https://www.cubecraft.net/forums/community-resources-safety.121/",
    "https://www.cubecraft.net/threads/allowed-mods-and-clients.228596/",
    "https://help.cubecraft.net/en/article/cubecraft-rules-1403lij/"
]

OUTPUT_FILE = "cubecraft_forum_data.jsonl"
file_lock = threading.Lock()
MAX_WORKERS = 25

# START FRESH: Clear output file completely and start with an empty set
with open(OUTPUT_FILE, "w", encoding="utf-8") as f:
    pass
scraped_urls = set()
print("[*] Started fresh from 0. Previous data cleared.")

def get_scraper():
    s = cloudscraper.create_scraper(
        browser={'browser': 'chrome', 'platform': 'windows', 'desktop': True}
    )
    s.headers.update({
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
        "Accept-Language": "en-US,en;q=0.9",
        "Referer": "https://www.cubecraft.net/",
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36"
    })
    return s

def scrape_thread(url):
    if url in scraped_urls:
        return None
        
    scraper = get_scraper()
    try:
        time.sleep(random.uniform(0.1, 0.6))  # Ultra-fast 0.1-0.6s delay
        t_res = scraper.get(url, timeout=10)
        if t_res.status_code != 200:
            return None
        
        t_soup = BeautifulSoup(t_res.text, "html.parser")
        title_elem = t_soup.find("h1", class_="p-title-value") or t_soup.find("h1")
        title = title_elem.text.strip() if title_elem else "CubeCraft Information"
        
        posts = []
        post_nodes = t_soup.find_all("article", class_="message") or t_soup.find_all("div", class_="message-inner") or t_soup.find_all("div", class_="article-content")
        
        for node in post_nodes:
            body = node.find("div", class_="bbWrapper") or node
            if body:
                for quote in body.find_all("blockquote"):
                    quote.decompose()
                text = body.get_text(separator=" ", strip=True)
                if len(text) > 20:
                    posts.append(text)
                    
        if not posts:
            main_body = t_soup.find("div", class_="p-body-main") or t_soup.find("body")
            if main_body:
                text = main_body.get_text(separator=" ", strip=True)
                if len(text) > 50:
                    posts.append(text[:2500])

        if posts:
            entry = {
                "system": "You are a CubeCraft Games assistant with deep knowledge of server mechanics and community discussions.",
                "instruction": f"Discuss or explain this CubeCraft topic: {title}",
                "input": "",
                "output": f"Content: {posts[0]}\n\nContext Details: {' '.join(posts[1:3]) if len(posts) > 1 else 'Official publication or guide.'}",
                "source_url": url
            }
            
            with file_lock:
                with open(OUTPUT_FILE, "a", encoding="utf-8") as f:
                    f.write(json.dumps(entry, ensure_ascii=False) + "\n")
                scraped_urls.add(url)
            return url
    except Exception:
        pass
    return None

print(f"=== FRESH ULTRA TURBO SCRAPER ({MAX_WORKERS} Workers, 0.1-0.6s) Active ===")
main_scraper = get_scraper()

for target in TARGET_URLS:
    if "/threads/" in target or "help.cubecraft.net" in target:
        print(f"\n[*] Scraping direct target page: {target}")
        scrape_thread(target)
        continue

    print(f"\n[*] Scanning forum section category: {target}")
    page = 1
    last_page_links = None

    while True:
        target_url = f"{target}page-{page}" if page > 1 else target
        
        try:
            time.sleep(random.uniform(0.1, 0.4))
            res = main_scraper.get(target_url, timeout=10)
            
            if res.status_code != 200 or "Page not found" in res.text:
                print(f"  -> Reached end of pagination at page {page-1}.")
                break
            
            soup = BeautifulSoup(res.text, "html.parser")
            
            thread_links = []
            for a in soup.find_all("a", href=True):
                href = a['href']
                if "/threads/" in href:
                    clean_href = href.split("/unread")[0].split("?")[0].rstrip("/") + "/"
                    full_url = BASE_URL + clean_href if clean_href.startswith("/") else clean_href
                    if full_url not in thread_links and full_url != BASE_URL + "/threads/":
                        thread_links.append(full_url)
            
            if not thread_links:
                print(f"  -> No threads found on page {page}.")
                break

            # CORRECTED Safeguard: Check if the ENTIRE page link list matches the previous page (true XenForo redirect)
            if page > 1 and set(thread_links) == set(last_page_links):
                print(f"  -> XenForo silent redirect detected at page {page} (mirrors previous page). Max page reached.")
                break
            last_page_links = thread_links

            print(f"  -> Scraping Page {page} ({len(thread_links)} threads) | Total saved: {len(scraped_urls)}")
            
            with ThreadPoolExecutor(max_workers=MAX_WORKERS) as executor:
                executor.map(scrape_thread, thread_links)
            
            gc.collect()
            page += 1
                    
        except Exception as e:
            print(f"  [!] Error on page {page}: {e}")
            break
            
print(f"\n[✔] Fresh scraping complete! Total unique items saved: {len(scraped_urls)}")
