import os, json, requests
from bs4 import BeautifulSoup
import gspread
from datetime import datetime, timezone, timedelta
import re
import datetime

# os.environ["LOGIN_URL"] = "https://reo-system.com/users/sign_in"
# os.environ["LOGIN_USER"] = "t.kawagoe"
# os.environ["LOGIN_PASS"] = "t.kawagoe"
# os.environ["LOGIN_SUCCESS_URL"] = "https://reo-system.com/sys/dashboard_royal/728"
# os.environ["WEB_BASE"] = "https://reo-system.com/"


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
    # 該当のreoB URLを取得
    top = session.get(os.environ['LOGIN_SUCCESS_URL'])
    top.raise_for_status()
    soup = BeautifulSoup(top.text, 'html.parser')

    # CSS セレクタで直接 a タグを取得
    a_tag = soup.select_one('.conditioning_input_status .conditioning_report_on a')
    if a_tag and a_tag.has_attr('href'):
        href = a_tag['href']    # => /pcm/conditioning_report/4667?transaction_status=900
        ymd = a_tag.text
        href_No = href.split("?")[0].split("/")[-1]
    else:
        print("リンクが見つかりませんでした")
        return

    # reoBへ移動
    href_reoB = os.environ["WEB_BASE"] + href + "?category=status&transaction_status=900"
    reoB = session.get(href_reoB)
    reoB.raise_for_status()
    soup = BeautifulSoup(reoB.text, 'html.parser')

    # (7) 対象のテーブルを取得（class="list sticky"）
    table = soup.find('table', class_='list sticky')
    tbody = table.find('tbody')

    # 日付取得
    m, d = [int(re.compile(r'[0-9０-９]+').findall(v)[0]) for v in ymd.split("/")[1:]]
    pattern = re.compile(rf'{m}/{d}|{m}月{d}日')

    # データ取得
    results = []
    for tr in tbody.find_all('tr'):
        # 現在時刻: TOKYO
        # JSTとUTCの差分
        DIFF_JST_FROM_UTC = 9
        dt_now = datetime.datetime.utcnow() + datetime.timedelta(hours=DIFF_JST_FROM_UTC)
        dt_now = dt_now.strftime('%Y/%m/%d %H:%M:%S')

    
        # 各セルのテキストをリスト化
        tds = tr.find_all('td')
        remarks = tds[-2].get_text(strip=True)
        if not pattern.search(remarks):
            continue
                
        row_data = [v.text for v in tr.find_all("td")]
        row_data[1] = row_data[1].replace("\n", "")
        row_data[7] = row_data[7].replace("\n\t\t\t\t\t", "").replace("\n\t\t\t", "")
        if tr.find('span', class_='change_10'):
            row_data[4] = "*"
        row_data = [dt_now, ymd, href_No] + row_data
        results.append(row_data[:-1])
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
