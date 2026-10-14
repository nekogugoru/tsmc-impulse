"""抓台積電（2330）最新收盤價，寫入 data/2330.json。

資料來源：臺灣證券交易所 STOCK_DAY（個股日成交資訊）。
只會寫入「已收盤」的交易日資料；今天還沒收盤或休市時，保留前一個交易日的價格。
"""
import json
import pathlib
import sys
import urllib.request
from datetime import datetime, timedelta, timezone

STOCK = "2330"
OUT = pathlib.Path(__file__).resolve().parent.parent / "data" / f"{STOCK}.json"
TPE = timezone(timedelta(hours=8))
UA = {"User-Agent": "Mozilla/5.0 (tsmc-impulse price updater)"}


def get_json(url):
    req = urllib.request.Request(url, headers=UA)
    with urllib.request.urlopen(req, timeout=30) as r:
        return json.loads(r.read().decode("utf-8"))


def roc_to_iso(s):
    """'115/10/14' -> '2026-10-14'"""
    y, m, d = s.strip().split("/")
    return f"{int(y) + 1911:04d}-{int(m):02d}-{int(d):02d}"


def to_num(s):
    return float(str(s).replace(",", "").strip())


def latest_close(now):
    """回傳 (date_iso, close)。查本月，若本月還沒有資料就查上個月。"""
    months = [now, now.replace(day=1) - timedelta(days=1)]
    for m in months:
        url = (
            "https://www.twse.com.tw/exchangeReport/STOCK_DAY"
            f"?response=json&date={m:%Y%m}01&stockNo={STOCK}"
        )
        data = get_json(url)
        if data.get("stat") != "OK" or not data.get("data"):
            continue
        fields = data.get("fields", [])
        i_date = fields.index("日期") if "日期" in fields else 0
        i_close = fields.index("收盤價") if "收盤價" in fields else 6
        for row in reversed(data["data"]):
            try:
                date_iso = roc_to_iso(row[i_date])
                close = to_num(row[i_close])
            except (ValueError, IndexError):
                continue  # 例如 '--' 表示當日無成交
            # 當天 13:30 前的資料視為尚未收盤
            if date_iso == now.strftime("%Y-%m-%d") and (now.hour, now.minute) < (13, 30):
                continue
            return date_iso, close
    raise RuntimeError("找不到收盤價資料")


def main():
    now = datetime.now(TPE)
    date_iso, close = latest_close(now)

    old = {}
    if OUT.exists():
        old = json.loads(OUT.read_text(encoding="utf-8"))
    if old.get("date") == date_iso and old.get("close") == close:
        print(f"沒有新資料，維持 {date_iso} 收盤 {close}")
        return 0

    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(
        json.dumps(
            {
                "stock": STOCK,
                "close": close,
                "date": date_iso,
                "updatedAt": now.isoformat(timespec="seconds"),
                "source": "TWSE STOCK_DAY",
            },
            ensure_ascii=False,
            indent=2,
        )
        + "\n",
        encoding="utf-8",
    )
    print(f"已更新：{date_iso} 收盤 {close}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
