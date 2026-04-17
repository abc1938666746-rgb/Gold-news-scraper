#!/usr/bin/env python3
"""
金十財經黃金新聞爬蟲
自動爬取金十財經網站的黃金相關快訊，並保存為 CSV 文件。

依賴庫:
    pip install requests beautifulsoup4 lxml

用法:
    python scraper.py
    python scraper.py --batches 5
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
FLASH_NEWEST_URL = "https://www.jin10.com/flash_newest.js"
FLASH_API_URL = "https://flash-api.jin10.com/get_flash_list"

GOLD_KEYWORDS = [
    "黃金", "金價", "XAUUSD", "XAU", "黃金期貨", "黃金現貨",
    "美聯儲", "Fed", "通脹", "避險", "金礦", "黃金ETF",
    "貴金屬", "黃金白銀", "金銀", "盎司", "黃金儲備",
]

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
    "x-app-id": "bVBF4FyRTn5NJF5n",
    "x-version": "1.0.0",
}


def is_gold_related(text: str) -> bool:
    text_lower = text.lower()
    return any(kw.lower() in text_lower for kw in GOLD_KEYWORDS)


def parse_items(raw_list: list) -> list[dict]:
    results = []
    for item in raw_list:
        data = item.get("data", {})
        content = data.get("content", "")
        title = data.get("title", "")
        combined = f"{title} {content}"

        if not is_gold_related(combined):
            continue

        ts = item.get("time", "")
        try:
            dt = datetime.strptime(ts, "%Y-%m-%d %H:%M:%S")
            time_str = dt.strftime("%Y-%m-%d %H:%M:%S")
        except Exception:
            time_str = ts

        item_id = item.get("id", "")
        results.append({
            "id": item_id,
            "time": time_str,
            "title": title,
            "content": content,
            "url": f"https://flash.jin10.com/detail/{item_id}" if item_id else "",
        })

    return results


def fetch_via_newest_js(session: requests.Session) -> list[dict]:
    """
    透過 flash_newest.js 抓取最新快訊（約 30 條）
    格式: var newest = [...];
    """
    try:
        resp = session.get(FLASH_NEWEST_URL, timeout=15)
        resp.raise_for_status()
        text = resp.text.strip()
        if text.startswith("var newest"):
            json_str = text[text.index("["):text.rindex("]") + 1]
            raw_list = json.loads(json_str)
            return parse_items(raw_list)
    except Exception as e:
        print(f"  [警告] flash_newest.js 解析失敗：{e}")
    return []


def fetch_via_api(max_time: str = None, session: requests.Session = None) -> tuple[list[dict], str]:
    """
    透過 Flash API 分批抓取歷史快訊
    Returns: (新聞列表, 最舊一條的 time 字串)
    """
    params = {
        "channel": "-8200",
        "classify": "0",
        "vip": "0",
        "action": "prev",
    }
    if max_time:
        params["max_time"] = max_time

    try:
        resp = session.get(FLASH_API_URL, params=params, timeout=15)
        resp.raise_for_status()
        data = resp.json()
        raw_list = data.get("data", [])
        if not raw_list:
            return [], ""
        items = parse_items(raw_list)
        oldest_time = raw_list[-1].get("time", "") if raw_list else ""
        return items, oldest_time
    except Exception as e:
        print(f"  [警告] API 請求失敗：{e}")
        return [], ""


def scrape_gold_news(num_batches: int = 5, delay: float = 1.5) -> list[dict]:
    session = requests.Session()
    session.headers.update(HEADERS)

    all_news = []
    seen_ids = set()

    print(f"開始爬取金十財經黃金新聞（共 {num_batches} 批）...")

    print("  第 1 批：透過 flash_newest.js 抓取最新快訊...", end=" ", flush=True)
    newest_items = fetch_via_newest_js(session)
    batch1_count = 0
    last_time = ""
    for item in newest_items:
        if item["id"] not in seen_ids:
            seen_ids.add(item["id"])
            all_news.append(item)
            batch1_count += 1
            if not last_time or item["time"] < last_time:
                last_time = item["time"]
    print(f"找到 {batch1_count} 條黃金相關新聞")

    for batch in range(2, num_batches + 1):
        time.sleep(delay)
        print(f"  第 {batch}/{num_batches} 批：抓取更早的快訊...", end=" ", flush=True)

        items, last_time = fetch_via_api(max_time=last_time, session=session)
        new_count = 0
        for item in items:
            if item["id"] not in seen_ids:
                seen_ids.add(item["id"])
                all_news.append(item)
                new_count += 1
        print(f"找到 {new_count} 條黃金相關新聞")

        if not last_time:
            break

    return all_news


def save_to_csv(news_list: list[dict], output_file: str = "gold_news.csv") -> None:
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
  python scraper.py --output gold_news_2026.csv
  python scraper.py --batches 10 --delay 2.0 --output output.csv
        """,
    )
    parser.add_argument(
        "--batches", type=int, default=5,
        help="爬取批次數量（默認: 5）",
    )
    parser.add_argument(
        "--delay", type=float, default=1.5,
        help="每批請求間隔秒數（默認: 1.5）",
    )
    parser.add_argument(
        "--output", type=str, default="gold_news.csv",
        help="輸出 CSV 文件名（默認: gold_news.csv）",
    )
    parser.add_argument(
        "--no-save", action="store_true",
        help="僅打印結果，不保存 CSV",
    )

    args = parser.parse_args()

    news = scrape_gold_news(num_batches=args.batches, delay=args.delay)
    print_summary(news)

    if not args.no_save:
        save_to_csv(news, output_file=args.output)


if __name__ == "__main__":
    main()
