import requests, json

url = "http://localhost:5000/open_external_video"
payload = {"camera_index": 0, "show_window": True, "output_fps": 5}

with requests.post(url, json=payload, stream=True) as r:
    r.raise_for_status()
    for line in r.iter_lines():
        if not line:
            continue
        data = json.loads(line.decode('utf-8'))
        print(data["joint_names"])
        print(data["angles"])      # 弧度，None 表示未检测到
        if not data.get("success", False):
            print("未检测到人")
        # 可以在这里做你自己的过滤/映射
