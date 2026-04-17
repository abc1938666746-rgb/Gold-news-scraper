# 金十財經黃金新聞爬蟲

自動爬取 [金十財經](https://www.jin10.com) 的黃金相關快訊，並保存為 CSV 文件。

## 功能

- 自動過濾與黃金相關的新聞（黃金、金價、XAUUSD、黃金期貨、美聯儲、通脹、避險等關鍵詞）
- 批次拉取金十財經快訊 API
- 輸出為 UTF-8 CSV 文件，方便 Excel 直接打開

## 安裝依賴

```bash
pip install -r requirements.txt
```

## 使用方法

```bash
# 基本用法（爬取 3 批，約 60 條，保存到 gold_news.csv）
python scraper.py

# 爬取更多批次
python scraper.py --batches 5

# 自定義輸出文件名
python scraper.py --output my_gold_news.csv

# 僅打印到終端，不保存
python scraper.py --no-save

# 全部參數
python scraper.py --batches 10 --delay 2.0 --output output.csv
```

## 參數說明

| 參數 | 說明 | 默認值 |
|------|------|--------|
| `--batches` | 爬取批次數，每批約 20 條 | `3` |
| `--delay` | 每批請求間隔秒數 | `1.5` |
| `--output` | 輸出 CSV 文件名 | `gold_news.csv` |
| `--no-save` | 僅打印，不保存 CSV | — |

## CSV 欄位說明

| 欄位 | 說明 |
|------|------|
| `id` | 新聞 ID |
| `time` | 發布時間（格式：YYYY-MM-DD HH:MM:SS） |
| `title` | 新聞標題（部分快訊無標題） |
| `content` | 新聞內容 |
| `url` | 原文鏈接 |

## 在 GitHub Actions 上定時運行

建立 `.github/workflows/scrape.yml`：

```yaml
name: 每日爬取黃金新聞

on:
  schedule:
    - cron: '0 2 * * *'   # 每天 UTC 02:00（北京時間 10:00）
  workflow_dispatch:        # 允許手動觸發

jobs:
  scrape:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4

      - name: 設置 Python
        uses: actions/setup-python@v5
        with:
          python-version: '3.11'

      - name: 安裝依賴
        run: pip install -r requirements.txt

      - name: 運行爬蟲
        run: python scraper.py --batches 5 --output gold_news.csv

      - name: 上傳結果
        uses: actions/upload-artifact@v4
        with:
          name: gold-news-${{ github.run_number }}
          path: gold_news.csv
```

## 注意事項

- 請勿過於頻繁請求，建議每批間隔至少 1.5 秒
- 本腳本僅供學習研究使用，請遵守網站使用條款
- 金十財經網站結構如有更新，可能需要調整爬取邏輯
