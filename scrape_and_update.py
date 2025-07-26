# main.py
import os, json, requests
from bs4 import BeautifulSoup
import gspread
from datetime import datetime, timedelta
import re
from oauth2client.service_account import ServiceAccountCredentials

# 環境変数はGitHub ActionsのSecretsにて設定される前提

def move2page(session, url):
    page = session.get(url)
    page.raise_for_status()
    soup = BeautifulSoup(page.text, 'html.parser')
    return soup

def login_and_get_session(session):
    soup = move2page(session, os.environ['LOGIN_URL'])
    auth_token = soup.select_one('input[name="authenticity_token"]')['value']

    payload = {
        'user[login]': os.environ['LOGIN_USER'],
        'user[password]': os.environ['LOGIN_PASS'],
        'authenticity_token': auth_token,
        'utf8': '✓',
        'commit': 'Log in',
        'user[remember_me]': '0',
    }
    headers = {
        'User-Agent': 'Mozilla/5.0',
        'Referer': os.environ['LOGIN_URL']
    }
    resp = session.post(os.environ['LOGIN_URL'], data=payload, headers=headers)
    resp.raise_for_status()

    if os.environ['LOGIN_SUCCESS_URL'] not in resp.url:
        raise RuntimeError("Login succeeded but landed on wrong page")

    return session

def go2condition(session):
    soup = move2page(session, os.environ['LOGIN_SUCCESS_URL'])
    a_tag = soup.select_one('.conditioning_input_status .conditioning_report_on a')
    if a_tag and a_tag.has_attr('href'):
        ymd_reo = a_tag.text
        href_number = a_tag['href'].split("?")[0].split("/")[-1]
        return [True, ymd_reo, href_number]
    return [False, '', '']

def reoB(session, ymd_reo, href_number):
    href = f"{os.environ['WEB_BASE']}pcm/conditioning_report/{href_number}?category=mt&transaction_status=900"
    soup = move2page(session, href)
    tbody = soup.find('table', class_='list sticky').find('tbody')

    results = []
    for tr in tbody.find_all('tr'):
        tds = tr.find_all('td')
        remarks = tds[-3].get_text(strip=True)
        if not remarks:
            continue
        row_data = [v.text.replace('\n', '') for v in tds]
        row_data[2] = '#' + row_data[2]
        temp = row_data[-3].split("\r\n")
        S, O, W = [temp[0], temp[-2] if len(temp) > 1 else '', temp[-1]]
        results.append([ymd_reo, href_number] + row_data + [S, O, W])
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
    return res.json()

def main():
    dt_now = (datetime.utcnow() + timedelta(hours=9)).strftime('%Y/%m/%d %H:%M:%S')
    session = requests.Session()
    ERROR_MESSAGE = [dt_now, '-', '-', '-', '-']

    # try:
    session = login_and_get_session(session)
    CHECK, ymd_reo, href_number = go2condition(session)
    if not CHECK:
        ERROR_MESSAGE[1] = "N"
    else:
        results = reoB(session, ymd_reo, href_number)
        if not results:
            ERROR_MESSAGE[1] = "D"
        else:
            creds_dict = json.loads(os.environ['GSPREAD_JSON'])
            scope = ['https://spreadsheets.google.com/feeds', 'https://www.googleapis.com/auth/drive']
            credentials = ServiceAccountCredentials.from_json_keyfile_dict(creds_dict, scope)
            gc = gspread.authorize(credentials)

            ws = gc.open_by_key(os.environ['SHEET_ID']).worksheet("reoB")
            ws.append_rows(results)
            ERROR_MESSAGE[1] = "O"

            res = send_to_viber(message_text=f"[reoB通知] {len(results)}件追加されました")
            ERROR_MESSAGE[2] = "O"
            ERROR_MESSAGE[3] = res.get("status", "")
            ERROR_MESSAGE[4] = res.get("status_message", "")

    # except Exception as e:
    #     print(f"ERROR: {e}")

    # 記録
    ws = gc.open_by_key(os.environ['SHEET_ID']).worksheet("record")
    ws.append_rows([ERROR_MESSAGE])

if __name__ == "__main__":
    main()
