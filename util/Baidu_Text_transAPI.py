# -*- coding: utf-8 -*-
import requests
import random
import json
from hashlib import md5

def translate_text(text,original_language="zh",target_language="en"):
    APP_ID = ''
    APP_KEY = ''

    url = 'http://api.fanyi.baidu.com/api/trans/vip/translate'

    def make_md5(s, encoding='utf-8'):
        return md5(s.encode(encoding)).hexdigest()

    salt = random.randint(32768, 65536)
    sign = make_md5(APP_ID + text + str(salt) + APP_KEY)

    # Build request
    headers = {'Content-Type': 'application/x-www-form-urlencoded'}
    payload = {'appid': APP_ID, 'q': text, 'from':original_language, 'to':target_language, 'salt': salt, 'sign': sign}

    # Send request
    r = requests.post(url, params=payload, headers=headers)
    result = r.json()

    translations = [translation['dst'] for translation in result['trans_result']]
    return '\n'.join(translations)

if __name__ == '__main__':
    query = 'Hello World! This is 1st paragraph.\nThis is 2nd paragraph.'
    translations = translate_text(query,"zh","zh")
    print(translations)
    translations = translate_text(query)
    print(translations)

