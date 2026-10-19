import requests
from urllib.parse import urlencode



import json

def build_json():
    with open("client_secret.json","r") as f:
        data = json.load(f)
    return data
def build_test_request():
    client_element = build_json()
    session = requests.session()

    query_params = {
        "client_id":client_element['web']['client_id'],
        "redirect_uri": client_element['web']['redirect_uris'][0],
        "response_type": "code",
        "scope": "https://www.googleapis.com/auth/userinfo.email https://www.googleapis.com/auth/userinfo.profile openid",

    }

    url = client_element['web']['auth_uri'] + "?" + urlencode(query_params)
    print(url)
if __name__ == '__main__':
    build_test_request()