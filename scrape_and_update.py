import os, json, requests
from bs4 import BeautifulSoup
import gspread
from datetime import datetime, timezone, timedelta
import re
import datetime
import requests


os.environ["LOGIN_URL"] = "https://reo-system.com/users/sign_in"
os.environ["LOGIN_USER"] = "t.kawagoe"
os.environ["LOGIN_PASS"] = "t.kawagoe"
os.environ["LOGIN_SUCCESS_URL"] = "https://reo-system.com/sys/dashboard_royal/728"
os.environ["WEB_BASE"] = "https://reo-system.com/"
os.environ["VIBER_AUTH_TOKEN"] = "55100e787c3944db-f25c732dbf670093-5785efa67ab2b224"
os.environ["VIBER_USER_ID"] = "eFRfZGOoL61kwaQjMC4eAQ=="


def move2page(session, url):
    page = session.get(url)
    page.raise_for_status()
    soup = BeautifulSoup(page.text, 'html.parser')
    return soup


def login_and_get_session(session):
    # (1) ログインページ取得 → authenticity_token 抜き出し
    soup = move2page(session, os.environ['LOGIN_URL'])
    auth_token = soup.select_one('input[name="authenticity_token"]')['value']

    # (3) ヘッダーを含めて POST
    payload = {
        'user[login]': os.environ['LOGIN_USER'],
        'user[password]': os.environ['LOGIN_PASS'],
        'authenticity_token': auth_token,
        'utf8': '✓',  # Rails form だと hidden で入ってることが多い
        'commit': 'Log in',  # ボタンの value に合わせる
        "user[remember_me]": "0",  # hidden フィールド
    }
    headers = {
        'User-Agent': 'Mozilla/5.0',
        'Referer': os.environ['LOGIN_URL']  # 直前に GET したページを Referer に
    }
    resp = session.post(os.environ['LOGIN_URL'], data=payload, headers=headers, allow_redirects=True)
    resp.raise_for_status()

    # (4) リダイレクト履歴と最終 URL を確認
    print("Redirect history:")
    for h in resp.history:
        print("  ", h.status_code, h.headers.get('Location'))

    # (5) 成功判定の強化
    expected_after_login = os.environ.get('LOGIN_SUCCESS_URL')
    if expected_after_login and expected_after_login not in resp.url:
        raise RuntimeError(f"Login succeeded (200) but did not land on expected page: {resp.url}")

    return session


def go2condition(session):
    # 該当のreoB URLを取得
    soup = move2page(session, os.environ['LOGIN_SUCCESS_URL'])

    # CSS セレクタで直接 a タグを取得
    a_tag = soup.select_one('.conditioning_input_status .conditioning_report_on a')
    if a_tag and a_tag.has_attr('href'):
        ymd_reo = a_tag.text
        href_number = a_tag['href'].split("?")[0].split("/")[-1]  # => /pcm/conditioning_report/4667?transaction_status=900
        return [True, ymd_reo, href_number]
    else:
        print("リンクが見つかりませんでした")
        return [False, "", ""]


def reoB(session, ymd_reo, href_number):
    # reoBStatusへ移動
    href_reoB = os.environ["WEB_BASE"] + f"pcm/conditioning_report/{href_number}" + "?category=mt&transaction_status=900"
    soup = move2page(session, href_reoB)

    # table
    table = soup.find('table', class_='list sticky')
    tbody = table.find('tbody')

    # データ取得
    results = []
    for tr in tbody.find_all('tr'):
        # 各セルのテキストをリスト化
        tds = tr.find_all('td')
        remarks = tds[-3].get_text(strip=True)
        if remarks == "":
            continue

        # データ取得
        row_data = [v.text for v in tr.find_all("td")]
        row_data[1] = row_data[1].replace("\n", "")
        row_data[2] = "#" + row_data[2]
        
        # SOAP
        temp = row_data[-3].split("\r\n")
        S, O, W = [temp[0], temp[-2] if len(temp) > 1 else "", temp[-1]]

        # 出力
        row_data = [ymd_reo, href_number] + row_data + [S, O, W]
        results.append(row_data)
        print(row_data)

    return results


def reoStatus(session, ymd_reo, href_number):
    # reoBStatusへ移動
    href_reoS = os.environ["WEB_BASE"] + f"pcm/conditioning_report/{href_number}" + "?category=status&transaction_status=900"
    soup = session.get(session, href_reoS)

    # table
    table = soup.find('table', class_='list sticky')
    tbody = table.find('tbody')

    # 当日の日付が入力されているかの確認
    m, d = [int(re.compile(r'[0-9０-９]+').findall(v)[0]) for v in ymd_reo.split("/")[1:]]
    pattern = re.compile(rf'{m}/{d}|{m}月{d}日')

    # データ取得
    results = []
    for tr in tbody.find_all('tr'):
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
        row_data = [dt_now, ymd_reo, href_number] + row_data
        results.append(row_data[:-1])
        print(row_data)

    return results


def send_to_viber(message_text):
    data = {
        "auth_token": os.environ["VIBER_AUTH_TOKEN"],
        "from": os.environ["VIBER_USER_ID"],
        "type": "text",
        "text": message_text
    }
    res = requests.post("https://chatapi.viber.com/pa/post", json=data)
    print(res.json())
    return res
    
def main():
    # 作動時刻
    DIFF_JST_FROM_UTC = 9
    dt_now = datetime.datetime.utcnow() + datetime.timedelta(hours=DIFF_JST_FROM_UTC)
    dt_now = dt_now.strftime('%Y/%m/%d %H:%M:%S')

    # start session
    session = requests.Session()
    RECORD_MESSAGE = [dt_now, "-", "-", "-", "-"]

    try:
        # reo認証
        session = login_and_get_session(session)

        # コンディショニング欄へ
        CHECK, ymd_reo, href_number = go2condition(session)

        # reo: B
        results = reoB(session, ymd_reo, href_number)
        if len(results) == 0:
            ERROR_MESSAGE[1] = "D" 
            
        else:
            # スプレッドシートの呼び出し
            creds_dict = json.loads(os.environ['GSPREAD_JSON'])
            gc = gspread.service_account_from_dict(creds_dict)

            # スプレッドシートに登録
            ws = gc.open_by_key(os.environ['SHEET_ID']).worksheet("reoB")
            ws.append_rows(results)
            ERROR_MESSAGE[1] = "O" 

            # viberに通知
            res = send_to_viber(message_text="test")
            ERROR_MESSAGE[2] = "O" 
            ERROR_MESSAGE[3] = res["status"]  
            ERROR_MESSAGE[4] = res["status_message"] 


    except:
        RECORD_MESSAGE[1] = "X"
        print(f"    {dt_now}: ERROR")

    
    # 記録の登録
    ws = gc.open_by_key(os.environ['SHEET_ID']).worksheet("record")
    ws.append_rows([RECORD_MESSAGE])

if __name__ == "__main__":
    main()
