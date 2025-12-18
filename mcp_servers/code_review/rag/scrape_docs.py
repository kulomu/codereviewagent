import os
import requests
from bs4 import BeautifulSoup
from markdownify import markdownify as md
from urllib.parse import urljoin
import shutil
import re

# ========== 設定區 ==========
SCRAPE_TARGETS = {
    "react_v18_learn": {
        "base_url": "https://18.react.dev",
        "start_paths": [
            "/learn/describing-the-ui",
            "/learn/adding-interactivity",
            "/learn/managing-state",
            "/learn/escape-hatches"
        ],
        "output_dir": "docs/react_v18_learn",
        "subpage_selector": "a[href^='/learn/']"  # 延伸子頁面
    },
    "react_v18_advanced": {
        "base_url": "https://18.react.dev",
        "start_paths": [
            "/reference/react/hooks",
            "/reference/react/components",
            "/reference/react/apis"
        ],
        "output_dir": "docs/react_v18_advanced",
        "subpage_selector": "a[href^='/reference/react/']"  # 延伸子頁
    }
}

CURRENT_TARGET = "react_v18_advanced"  # 這裡改來切換不同網站
# =============================

def fetch_html(url):
    response = requests.get(url)
    response.raise_for_status()
    return response.text

def parse_subpage_links(html, selector, base_url):
    if not selector:
        return []

    soup = BeautifulSoup(html, "html.parser")
    links = soup.select(selector)
    subpages = set()

    for link in links:
        href = link.get("href")
        if href and href.startswith("/") and href != base_url:
            subpages.add(urljoin(base_url, href))

    return list(subpages)

def save_markdown(title, html, output_path):
    md_content = md(html)

    # 將標題轉換為 snake_case 檔案名
    def to_snake_case(text):
        text = text.strip().lower()
        text = re.sub(r"[^\w\s-]", "", text)  # 移除特殊符號
        text = re.sub(r"[\s\-]+", "_", text)  # 空白與 dash 變為底線
        return text

    filename = to_snake_case(title) + ".md"
    full_path = os.path.join(output_path, filename)

    with open(full_path, "w", encoding="utf-8") as f:
        f.write(f"# {title}\n\n")
        f.write(md_content)
    print(f"✅ Saved: {full_path}")


def main():
    config = SCRAPE_TARGETS[CURRENT_TARGET]
    base_url = config["base_url"]
    start_paths = config["start_paths"]
    output_dir = config["output_dir"]
    subpage_selector = config["subpage_selector"]

    # 先清空 output 資料夾
    if os.path.exists(output_dir):
        print(f"🧹 清空舊資料夾：{output_dir}")
        shutil.rmtree(output_dir)
    os.makedirs(output_dir, exist_ok=True)

    visited = set()

    for path in start_paths:
        full_url = urljoin(base_url, path)
        print(f"🔍 Fetching main page: {full_url}")
        main_html = fetch_html(full_url)

        subpage_urls = parse_subpage_links(main_html, subpage_selector, base_url)
        subpage_urls.insert(0, full_url)

        for url in subpage_urls:
            if url in visited:
                continue
            visited.add(url)
            print(f"📄 Fetching: {url}")
            html = fetch_html(url)
            soup = BeautifulSoup(html, "html.parser")
            article = soup.select_one("article") or soup.select_one("[data-testid='learn-page-content']")
            title = soup.title.string.strip().split("–")[0] if soup.title else "untitled"

            if article:
                save_markdown(title, str(article), output_dir)
            else:
                print(f"⚠️ 沒找到文章內容：{url}")

if __name__ == "__main__":
    main()
