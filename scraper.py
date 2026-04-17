#!/usr/bin/env python3
"""
金十財經黃金新聞爬蟲
自動爬取金十財經網站的黃金相關新聞，並保存為 CSV 文件。

依賴庫:
    pip install requests beautifulsoup4 lxml

用法:
    python scraper.py
    python scraper.py --pages 5
    python scraper.py --output my_news.csv
"""

import argparse
import csv
import json
import time
import sys
from datetime import datetime
from urllib.parse import urljoin

try:
    import requests
    from bs4 import BeautifulSoup
except ImportError:
    print("缺少依賴庫，請先安裝：pip install requests beautifulsoup4 lxml")
    sys.exit(1)


BASE_URL = "https://www.jin10.com"
NEWS_API_URL = "https://flash-api.jin10.com/get_flash_list"
GOLD_KEYWORDS = ["黃金", "金價", "XAUUSD", "黃金期貨", "黃金現貨", "美聯儲", "通脹", "避險", "金礦", "黃金ETF"]

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/120.0.0.0 Safari/537.36"
    ),
    "Accept": "application/json, text/plain, */*",
    "Accept-Language": "zh-TW,zh;q=0.9,en;q=0.8",
    "Referer": "https://www.jin10.com/",
    "Origin": "https://www.jin10.com",
}


def is_gold_related(text: str) -> bool:
    """判斷文字是否與黃金相關"""
    return any(kw in text for kw in GOLD_KEYWORDS)


def fetch_flash_news(max_id: str = None, session: requests.Session = None) -> dict:
    """從金十財經 Flash API 獲取快訊列表"""
    if session is None:
        session = requests.Session()
        session.headers.update(HEADERS)

    params = {
        "channel": "-8200",
        "classify": "0",
        "vip": "0",
        "action": "prev",
    }
    if max_id:
        params["max_time"] = max_id

    try:
        resp = session.get(NEWS_API_URL, params=params, timeout=15)
        resp.raise_for_status()
        return resp.json()
    except requests.RequestException as e:
        print(f"  [警告] 請求失敗：{e}")
        return {}
    except json.JSONDecodeError:
        print("  [警告] 無法解析 JSON 回應")
        return {}


def parse_flash_items(data: dict) -> list[dict]:
    """解析快訊列表中的每筆資料"""
    items = data.get("data", {})
    if not items:
        return []

    results = []
    for item in items:
        content = item.get("data", {}).get("content", "")
        title = item.get("data", {}).get("title", "")
        combined = f"{title} {content}"

        if not is_gold_related(combined):
            continue

        ts = item.get("time", "")
        try:
            dt = datetime.fromtimestamp(int(ts))
            time_str = dt.strftime("%Y-%m-%d %H:%M:%S")
        except (ValueError, TypeError):
            time_str = ts

        results.append({
            "id": item.get("id", ""),
            "time": time_str,
            "timestamp": ts,
            "title": title,
            "content": content,
            "url": urljoin(BASE_URL, f"/detail/{item.get('id', '')}"),
        })

    return results


def fetch_news_page(page: int = 1, session: requests.Session = None) -> list[dict]:
    """爬取金十財經黃金頻道頁面（備用方案）"""
    if session is None:
        session = requests.Session()
        session.headers.update(HEADERS)

    url = f"{BASE_URL}/gold.html"
    try:
        resp = session.get(url, timeout=15)
        resp.raise_for_status()
    except requests.RequestException as e:
        print(f"  [警告] 頁面請求失敗：{e}")
        return []

    soup = BeautifulSoup(resp.text, "lxml")
    items = []

    for article in soup.select(".article-list-item, .news-item, .flash-item"):
        title_tag = article.select_one("h2, h3, .title, .news-title")
        link_tag = article.select_one("a")
        time_tag = article.select_one("time, .time, .date, .pub-time")
        desc_tag = article.select_one("p, .desc, .summary, .content")

        title = title_tag.get_text(strip=True) if title_tag else ""
        link = link_tag.get("href", "") if link_tag else ""
        if link and not link.startswith("http"):
            link = urljoin(BASE_URL, link)
        pub_time = time_tag.get_text(strip=True) if time_tag else ""
        desc = desc_tag.get_text(strip=True) if desc_tag else ""

        if not is_gold_related(f"{title} {desc}"):
            continue

        items.append({
            "id": "",
            "time": pub_time,
            "timestamp": "",
            "title": title,
            "content": desc,
            "url": link,
        })

    return items


def scrape_gold_news(num_batches: int = 3, delay: float = 1.5) -> list[dict]:
    """
    主爬蟲函數：持續從 Flash API 拉取，直到達到指定批次數量

    Args:
        num_batches: 拉取批次數量（每批約 20 條）
        delay:       每批間隔秒數（避免頻繁請求）

    Returns:
        list: 所有黃金相關新聞
    """
    session = requests.Session()
    session.headers.update(HEADERS)

    all_news = []
    seen_ids = set()
    last_timestamp = None

    print(f"開始爬取金十財經黃金新聞（共 {num_batches} 批）...")

    for batch in range(1, num_batches + 1):
        print(f"  正在爬取第 {batch}/{num_batches} 批...", end=" ", flush=True)

        data = fetch_flash_news(max_id=last_timestamp, session=session)
        items = parse_flash_items(data)

        new_count = 0
        for item in items:
            if item["id"] and item["id"] in seen_ids:
                continue
            if item["id"]:
                seen_ids.add(item["id"])
            all_news.append(item)
            new_count += 1
            if item["timestamp"]:
                if last_timestamp is None or item["timestamp"] < last_timestamp:
                    last_timestamp = item["timestamp"]

        print(f"找到 {new_count} 條黃金相關新聞")

        if batch < num_batches:
            time.sleep(delay)

    if not all_news:
        print("Flash API 未返回數據，嘗試備用頁面爬取...")
        all_news = fetch_news_page(session=session)

    return all_news


def save_to_csv(news_list: list[dict], output_file: str = "gold_news.csv") -> None:
    """將新聞列表保存為 CSV 文件"""
    if not news_list:
        print("沒有數據可保存。")
        return

    fieldnames = ["id", "time", "title", "content", "url"]
    with open(output_file, "w", newline="", encoding="utf-8-sig") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames, extrasaction="ignore")
        writer.writeheader()
        writer.writerows(news_list)

    print(f"\n已保存 {len(news_list)} 條新聞到 {output_file}")


def print_summary(news_list: list[dict]) -> None:
    """在終端打印新聞摘要"""
    print(f"\n{'=' * 60}")
    print(f"共找到 {len(news_list)} 條黃金相關新聞")
    print(f"{'=' * 60}")
    for i, item in enumerate(news_list[:10], start=1):
        print(f"\n[{i}] {item['time']}")
        if item["title"]:
            print(f"    標題：{item['title']}")
        content = item["content"]
        if len(content) > 80:
            content = content[:80] + "..."
        print(f"    內容：{content}")
        print(f"    鏈接：{item['url']}")
    if len(news_list) > 10:
        print(f"\n... 共 {len(news_list)} 條，已輸出前 10 條。完整數據請查看 CSV 文件。")


def main():
    parser = argparse.ArgumentParser(
        description="金十財經黃金新聞爬蟲",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
範例:
  python scraper.py
  python scraper.py --batches 5
  python scraper.py --output gold_news_2025.csv
  python scraper.py --batches 10 --delay 2.0 --output output.csv
        """,
    )
    parser.add_argument(
        "--batches",
        type=int,
        default=3,
        help="爬取批次數量，每批約 20 條新聞（默認: 3）",
    )
    parser.add_argument(
        "--delay",
        type=float,
        default=1.5,
        help="每批請求間隔秒數（默認: 1.5）",
    )
    parser.add_argument(
        "--output",
        type=str,
        default="gold_news.csv",
        help="輸出 CSV 文件名（默認: gold_news.csv）",
    )
    parser.add_argument(
        "--no-save",
        action="store_true",
        help="僅打印結果，不保存 CSV",
    )

    args = parser.parse_args()

    news = scrape_gold_news(num_batches=args.batches, delay=args.delay)
    print_summary(news)

    if not args.no_save:
        save_to_csv(news, output_file=args.output)


if __name__ == "__main__":
    main()
