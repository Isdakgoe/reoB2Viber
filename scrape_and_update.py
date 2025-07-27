
import os, json, requests
import pandas as pd
from bs4 import BeautifulSoup
import gspread
from datetime import datetime, timezone, timedelta
import re
import datetime
import requests


def login_and_get_session(session):
    # (1) ログインページ取得 → authenticity_token 抜き出し
    soup = _move2page(session, os.environ['LOGIN_URL'])
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

    # (６) REOへログイン
    soup = _move2page(session, os.environ['LOGIN_SUCCESS_URL'])
    a_tag = soup.select_one('.conditioning_input_status .conditioning_report_on a')
    if a_tag and a_tag.has_attr('href'):
        ymd_reo = a_tag.text
        href_number = a_tag['href'].split("?")[0].split("/")[-1]  # => /pcm/conditioning_report/4667?transaction_status=900
        return [session, ymd_reo, href_number]
    else:
        return ["", "", ""]


def _move2page(session, url):
    page = session.get(url)
    page.raise_for_status()
    soup = BeautifulSoup(page.text, 'html.parser')
    return soup


def reoB(session, ymd_reo, href_number, category, remarks_col, remarks_value):
    # get table
    df = _reo_table_download(session, ymd_reo, href_number, category, remarks_col, remarks_value)
    
    # SOAP
    temp = df.iloc[:, -3].str.split("\r\n")
    df["S"] = temp.str[1]
    df["O"] = temp.str[-2]
    df["W"] = temp.str[-1]

    # viber
    text0 = ymd_reo + " B欄\n\n"
    text1 = "\n\n\n".join([f"{v[2]}  {v[6]}  {v[15]}\n   {v[13]}\n   {v[14]}\n" for v in df[df[2] == "投手"].values])
    text2 = "\n\n\n".join([f"{v[2]}  {v[6]}  {v[15]}\n   {v[13]}\n   {v[14]}\n" for v in df[df[2] != "投手"].values])
    text = text0 + f"===== 投手 =====\n" + text1 + f"\n\n===== 野手 =====\n" + text2

    # sheet
    results = [list(v) for v in df.values]

    return results, text


def reoC(session, ymd_reo, href_number, category, remarks_col, remarks_value):
    # get table
    df = _reo_table_download(session, ymd_reo, href_number, category, remarks_col, remarks_value)

    # 体重および体重前日比
    df["weight"] = df[9].str.split("\n").str[1].str.replace(" ", "").str[:-2]
    df["weight_comp"] = df[9].str.split("\n").str[3].str.replace(" ", "")

    # viber
    text0 = ymd_reo + " C欄 体重\n\n"
    text1 = "\n".join([f"{v[2]}  {v[-2]:>5}kg {v[-1]}\n" for v in df[df[2] == "投手"].values])
    text2 = "\n".join([f"{v[2]}  {v[-2]:>5}kg {v[-1]}\n" for v in df[df[2] != "投手"].values])
    text = text0 + f"===== 投手 =====\n" + text1 + f"\n\n===== 野手 =====\n" + text2

    # sheet
    results = [list(v) for v in df.values]
    return results, text


def _reo_table_download(session, ymd_reo, href_number, category, remarks_col, remarks_value):
    # reoの各ページへ移動
    href_reo = os.environ["WEB_BASE"] + f"pcm/conditioning_report/{href_number}" + f"?category={category}&transaction_status=900"
    soup = _move2page(session, href_reo)

    # table
    table = soup.find('table', class_='list sticky')
    tbody = table.find('tbody')
    results = [[v.text for v in tr.find_all('td')] for tr in tbody.find_all('tr')]

    # DataFrame
    df = pd.DataFrame(results)
    df = df[df[remarks_col] != remarks_value].copy()
    df[-3] = ymd_reo
    df[-2] = href_number
    df[-1] = "#" + df[0] + df[1].str.replace("\n", "").str.split("\u3000").str[0]
    df = df[sorted(df.columns)]
    return df


def send_to_viber(message_text):
    data = {
        "auth_token": os.environ["VIBER_AUTH_TOKEN"],
        "from": os.environ["VIBER_USER_ID"],
        "type": "text",
        "text": message_text
    }
    res = requests.post("https://chatapi.viber.com/pa/post", json=data)
    print(res.json())
    return res.json()


def upload2sheet(gc, ERROR_MESSAGE, sheet_name, list, text, info_number):
    # sheet
    ws = gc.open_by_key(os.environ['SHEET_ID']).worksheet(sheet_name)
    ws.append_rows(list)

    # viber
    res = send_to_viber(message_text=text)

    # record
    ERROR_MESSAGE[info_number] = len(list)
    ERROR_MESSAGE[info_number + 1] = res["status"]
    ERROR_MESSAGE[info_number + 2] = res["status_message"]

    return ERROR_MESSAGE


def main():
    # 作動時刻
    DIFF_JST_FROM_UTC = 9
    dt_now = datetime.datetime.utcnow() + datetime.timedelta(hours=DIFF_JST_FROM_UTC)
    dt_now = dt_now.strftime('%Y/%m/%d %H:%M:%S')

    # start session
    session = requests.Session()
    ERROR_MESSAGE = [dt_now, "-", "-", "-", "-", "-", "-"]

    # reo認証
    session, ymd_reo, href_number = login_and_get_session(session)

    # reo取得
    reoB_results, reoB_viber = reoB(session, ymd_reo, href_number, category="mt", remarks_col=7, remarks_value='')
    reoC_results, reoC_viber = reoC(session, ymd_reo, href_number, category="training", remarks_col=9, remarks_value='\n\n          (-)\n        \n')

    # スプレッドシートの呼び出し
    creds_dict = json.loads(os.environ['GSPREAD_JSON'])
    gc = gspread.service_account_from_dict(creds_dict)
    ERROR_MESSAGE = upload2sheet(gc, ERROR_MESSAGE, sheet_name="reoB", list=reoB_results, text=reoB_viber, info_number=1)
    ERROR_MESSAGE = upload2sheet(gc, ERROR_MESSAGE, sheet_name="reoC", list=reoC_results, text=reoC_viber, info_number=4)

    # 記録の登録
    ws = gc.open_by_key(os.environ['SHEET_ID']).worksheet("record")
    ws.append_rows([ERROR_MESSAGE])


if __name__ == "__main__":
    main()
