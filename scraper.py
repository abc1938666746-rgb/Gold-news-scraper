#!/usr/bin/env python3
"""
金十財經黃金新聞爬蟲
自動爬取金十財經網站的黃金相關快訊，並保存為 CSV 文件。

依賴庫:
    pip install requests beautifulsoup4 lxml

用法:
    python scraper.py
    python scraper.py --batches 20
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

# 使用簡體中文關鍵詞（金十 API 返回的是簡體中文）
# 注意：「黄」(U+9EC4) 與「黃」(U+9EC3) 是不同字符
GOLD_KEYWORDS = [
    "黄金",        # 簡體「黃金」
    "金价",        # 簡體「金價」
    "XAUUSD",
    "XAU/USD",
    "XAU",
    "黄金期货",    # 黃金期貨
    "黄金现货",    # 黃金現貨
    "贵金属",      # 貴金屬
    "黄金储备",    # 黃金儲備
    "黄金ETF",
    "黄金白银",
    "Gold ETF",
    "gold",        # 英文
    "Gold",
    "GOLD",
    "盎司",        # 黃金以盎司計價
    "现货黄金",
    "伦敦金",
    "纽约黄金",
    "黄金矿",
]

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/120.0.0.0 Safari/537.36"
    ),
    "Accept": "application/json, text/plain, */*",
    "Accept-Language": "zh-CN,zh;q=0.9,en;q=0.8",
    "Referer": "https://www.jin10.com/",
    "Origin": "https://www.jin10.com",
    "x-app-id": "bVBF4FyRTn5NJF5n",
    "x-version": "1.0.0",
}


def is_gold_related(text: str) -> bool:
    for kw in GOLD_KEYWORDS:
        if kw.lower() in text.lower():
            return True
    return False


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
        item_id = item.get("id", "")

        results.append({
            "id": item_id,
            "time": ts,
            "title": title,
            "content": BeautifulSoup(content, "lxml").get_text() if "<" in content else content,
            "url": f"https://flash.jin10.com/detail/{item_id}" if item_id else "",
        })

    return results


def fetch_via_newest_js(session: requests.Session) -> tuple[list[dict], str]:
    """透過 flash_newest.js 抓取最新快訊（約 50 條），返回 (新聞列表, 最舊ID)"""
    try:
        resp = session.get(FLASH_NEWEST_URL, timeout=15)
        resp.raise_for_status()
        text = resp.text.strip()
        if "var newest" in text:
            json_str = text[text.index("["):text.rindex("]") + 1]
            raw_list = json.loads(json_str)
            items = parse_items(raw_list)
            oldest_id = raw_list[-1].get("id", "") if raw_list else ""
            return items, oldest_id
    except Exception as e:
        print(f"  [警告] flash_newest.js 解析失敗：{e}")
    return [], ""


def fetch_via_api(max_id: str = None, session: requests.Session = None) -> tuple[list[dict], str]:
    """透過 Flash API 分批抓取歷史快訊，使用 ID 分頁"""
    params = {
        "channel": "-8200",
        "classify": "0",
        "vip": "0",
        "action": "prev",
    }
    if max_id:
        params["max_id"] = max_id

    try:
        resp = session.get(FLASH_API_URL, params=params, timeout=15)
        resp.raise_for_status()
        data = resp.json()
        raw_list = data.get("data", [])
        if not raw_list:
            return [], ""
        items = parse_items(raw_list)
        oldest_id = raw_list[-1].get("id", "") if raw_list else ""
        return items, oldest_id
    except Exception as e:
        print(f"  [警告] API 請求失敗：{e}")
        return [], ""


def scrape_gold_news(num_batches: int = 20, delay: float = 1.5) -> list[dict]:
    session = requests.Session()
    session.headers.update(HEADERS)

    all_news = []
    seen_ids = set()
    last_id = ""

    print(f"開始爬取金十財經黃金新聞（共 {num_batches} 批，每批約 20 條）...")
    print(f"使用關鍵詞：{', '.join(GOLD_KEYWORDS[:8])} 等 {len(GOLD_KEYWORDS)} 個\n")

    print("  第 1 批：透過最新快訊接口抓取...", end=" ", flush=True)
    items, last_id = fetch_via_newest_js(session)
    count = 0
    for item in items:
        if item["id"] not in seen_ids:
            seen_ids.add(item["id"])
            all_news.append(item)
            count += 1
    print(f"找到 {count} 條黃金相關新聞")

    for batch in range(2, num_batches + 1):
        time.sleep(delay)
        print(f"  第 {batch}/{num_batches} 批：抓取更早的快訊...", end=" ", flush=True)

        items, new_last_id = fetch_via_api(max_id=last_id, session=session)

        if not new_last_id:
            print("(無更多數據，停止)")
            break

        new_count = 0
        for item in items:
            if item["id"] not in seen_ids:
                seen_ids.add(item["id"])
                all_news.append(item)
                new_count += 1
        print(f"找到 {new_count} 條黃金相關新聞")
        last_id = new_last_id

    return all_news


def save_to_csv(news_list: list[dict], output_file: str = "gold_news.csv") -> None:
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
        print(f"\n... 共 {len(news_list)} 條，前 10 條如上。完整數據請查看 CSV 文件。")


def main():
    parser = argparse.ArgumentParser(
        description="金十財經黃金新聞爬蟲",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
範例:
  python scraper.py
  python scraper.py --batches 20
  python scraper.py --output gold_news_2026.csv
  python scraper.py --batches 30 --delay 2.0 --output output.csv
        """,
    )
    parser.add_argument("--batches", type=int, default=20,
                        help="爬取批次數量，每批約 20 條（默認: 20，即約 400 條新聞）")
    parser.add_argument("--delay", type=float, default=1.5,
                        help="每批請求間隔秒數（默認: 1.5）")
    parser.add_argument("--output", type=str, default="gold_news.csv",
                        help="輸出 CSV 文件名（默認: gold_news.csv）")
    parser.add_argument("--no-save", action="store_true",
                        help="僅打印結果，不保存 CSV")

    args = parser.parse_args()

    news = scrape_gold_news(num_batches=args.batches, delay=args.delay)
    print_summary(news)

    if not args.no_save:
        if news:
            save_to_csv(news, output_file=args.output)
        else:
            print("\n本次爬取未找到黃金相關新聞（可能是當前新聞以其他話題為主）")
            print("建議增加 --batches 數量或換個時段重試")


if __name__ == "__main__":
    main()
