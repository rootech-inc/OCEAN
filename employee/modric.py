import json
from ocean.settings import ATTENDANCE_URL


def token(username,password):
    url = f'{ATTENDANCE_URL}jwt-api-token-auth/'
    print(f"AUTH_URL: {url}")
    data = {
        'username':username,
        'password':password
    }



    header = {
        'Content-Type':'application/json'
    }

    import requests
    response = requests.post(url,json=data,headers=header)
    token = json.loads(response.text).get('token')
    print(token)
    print(response.text)
    print("hello")
    return token