import os, json, requests
from bs4 import BeautifulSoup
import gspread
from datetime import datetime, timezone, timedelta

def main():
    # 1) 認証情報を dict としてロード
    creds_dict = json.loads(os.environ['GSPREAD_JSON'])
    creds_dict["private_key"] = creds_dict["private_key"].replace("\\n", "\n")
    gc = gspread.service_account_from_dict(creds_dict)

    # 2) シートを開く
    sheet_id = os.environ['SHEET_ID']
    ws = gc.open_by_key(sheet_id).sheet1

    ws.append_rows(["1", "2"])
    print(f"Appended {len(to_append)} new rows.")

    # # 3) 既存 URL を取得 (列2 をキーに)
    # all_vals = ws.get_all_values()
    # existing = {row[1] for row in all_vals if len(row) > 1}

    # # 4) 実行日 (JST) 文字列
    # now_utc = datetime.now(timezone.utc)
    # run_date = (now_utc + timedelta(hours=9)).strftime('%Y/%m/%d')

    # # 5) スクレイピング＋フィルタリング
    # to_append = []
    # for i in range(1, 31):
    #     url = f'https://example.com/page/{i}'
    #     r = requests.get(url, timeout=10)
    #     r.raise_for_status()
    #     soup = BeautifulSoup(r.text, 'html.parser')
    #     if url in existing:
    #         continue
    #     title = soup.select_one('h1.title').get_text(strip=True)
    #     date  = soup.select_one('time').get('datetime')
    #     to_append.append([run_date, url, title, date])

    # # 6) シートに追記
    # if to_append:
    #     ws.append_rows(to_append)
    #     print(f"Appended {len(to_append)} new rows.")
    # else:
    #     print("No new data to append.")

if __name__ == "__main__":
    main()
