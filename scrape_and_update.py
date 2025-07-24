
import os, json, requests
from bs4 import BeautifulSoup
import gspread
from datetime import datetime, timezone, timedelta
import re

def login_and_get_session():
    session = requests.Session()

    # (1) ログインページ取得 → authenticity_token 抜き出し
    login_page = session.get(os.environ['LOGIN_URL'])
    login_page.raise_for_status()
    soup = BeautifulSoup(login_page.text, 'html.parser')
    auth_token = soup.select_one('input[name="authenticity_token"]')['value']

    # (2) 認証情報
    username = os.environ['LOGIN_USER']
    password = os.environ['LOGIN_PASS']

    # (3) ヘッダーを含めて POST
    payload = {
         'user[login]': username,
         'user[password]': password,
         'authenticity_token': auth_token,
         'utf8': '✓',  # Rails form だと hidden で入ってることが多い
         'commit': 'Log in',  # ボタンの value に合わせる
         "user[remember_me]": "0",               # hidden フィールド
    }
    headers = {
        'User-Agent': 'Mozilla/5.0',
        'Referer': os.environ['LOGIN_URL']  # 直前に GET したページを Referer に
    }
    resp = session.post(os.environ['LOGIN_URL'], data=payload, headers=headers, allow_redirects=True)
    resp.raise_for_status()

    # (4) リダイレクト履歴と最終 URL を確認
    print("Login response URL:", resp.url)
    print("Redirect history:")
    for h in resp.history:
        print("  ", h.status_code, h.headers.get('Location'))

    # (5) 成功判定の強化
    expected_after_login = os.environ.get('LOGIN_SUCCESS_URL')
    if expected_after_login and expected_after_login not in resp.url:
        raise RuntimeError(f"Login succeeded (200) but did not land on expected page: {resp.url}")

    return session


def reoB(session):
    # (6) データ取得
    reoB = session.get(os.environ['reoB'])
    reoB.raise_for_status()
    soup = BeautifulSoup(reoB.text, 'html.parser')

    # 日付の取得
    date_pattern = re.compile(r'[7７](?:[／/]|月)[2２][3３]日?')

    # (7) 対象のテーブルを取得（class="list sticky"）
    table = soup.find('table', class_='list sticky')
    tbody = table.find('tbody')
    
    # データ取得
    results = []
    for tr in tbody.find_all('tr'):
        # 各セルのテキストをリスト化
        tds = tr.find_all('td')
        remarks = tds[-2].get_text(strip=True)
        if not date_pattern.search(remarks):
            continue

        row_data = [v.text for v in tr.find_all("td")]
        row_data[1] = row_data[1].replace("\n", "")
        row_data[7] = row_data[7].replace("\n\t\t\t\t\t", "").replace("\n\t\t\t", "")
        if tr.find('span', class_='change_10'):
            row_data[4] = "*"

        results.append(row_data[-1])
        print(row_data)

    return results


def main():
    # 認証付きセッションの取得
    session = login_and_get_session()

    # 取得
    results = reoB(session)
    if len(results) == 0:
        print("No new data to append.")
    else:
        # スプレッドシートの呼び出し
        creds_dict = json.loads(os.environ['GSPREAD_JSON'])
        gc = gspread.service_account_from_dict(creds_dict)
        ws = gc.open_by_key(os.environ['SHEET_ID']).sheet1
        ws.append_rows(results)
        print(f"Appended {len(results)} new rows.")


if __name__ == "__main__":
    main()
