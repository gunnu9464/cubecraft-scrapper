from curl_cffi import requests
from bs4 import BeautifulSoup
import json
import time
import random
import os
from concurrent.futures import ThreadPoolExecutor
import threading
import gc

BASE_URL = "https://www.cubecraft.net"

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

with open(OUTPUT_FILE, "w", encoding="utf-8") as f:
    pass
scraped_urls = set()
print("[*] Started fresh from 0. Previous data cleared.")

def scrape_thread(url):
    if url in scraped_urls:
        return None
        
    try:
        time.sleep(random.uniform(0.1, 0.6))
        # Use curl_cffi to impersonate Chrome TLS fingerprint
        t_res = requests.get(url, impersonate="chrome", timeout=10)
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

print(f"=== CURL-CFFI TURBO SCRAPER ({MAX_WORKERS} Workers) Active ===")

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
            res = requests.get(target_url, impersonate="chrome", timeout=10)
            
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

            if page > 1 and set(thread_links) == set(last_page_links):
                print(f"  -> XenForo silent redirect detected at page {page}. Max page reached.")
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
            
print(f"\n[✔] Scraping complete! Total unique items saved: {len(scraped_urls)}")
