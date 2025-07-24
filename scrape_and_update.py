import os, requests
from bs4 import BeautifulSoup
import gspread
from oauth2client.service_account import ServiceAccountCredentials
from datetime import datetime, timezone, timedelta

# 1) 認証設定
json_key = os.environ['GSPREAD_JSON']
# sheet_id = os.environ['SHEET_ID']
# with open('/tmp/creds.json','w') as f:
#     f.write(json_key)
# creds = ServiceAccountCredentials.from_json_keyfile_name(
#     '/tmp/creds.json',
#     ['https://spreadsheets.google.com/feeds','https://www.googleapis.com/auth/drive']
# )
# gc = gspread.authorize(creds)
# ws = gc.open_by_key(sheet_id).sheet1

# # 2) 既存 URL 取得 (列2)
# all_vals = ws.get_all_values()
# existing = {row[1] for row in all_vals if len(row) > 1}

# # 3) 実行日 (JST)
# now_utc = datetime.now(timezone.utc)
# run_date = (now_utc + timedelta(hours=9)).strftime('%Y/%m/%d')

# # 4) スクレイピング + フィルタリング
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

# # 5) シートに追記
# if to_append:
#     ws.append_rows(to_append)
#     print(f"Appended {len(to_append)} rows.")
# else:
    # print("No new data to append.")
