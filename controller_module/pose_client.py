import requests
import threading
import mimetypes
from contextlib import ExitStack
import threading
import os
import mimetypes
from contextlib import ExitStack
import json
import contextlib

# 分离单张与连续动作两个接口
POSE_SERVER_URL_SINGLE = 'http://192.168.43.153:5000/analyze_pose'        # 单张图片接口
POSE_SERVER_URL_SEQUENCE = 'http://192.168.43.153:5000/analyze_pose_batch' # 连续动作接口

def get_pose_from_image(image_path, timeout=30):
    """
    发送图片到姿态估计服务器，返回关节角度结果。
    :param image_path: 图片文件路径
    :return: 关节角度（dict或list，取决于服务端返回格式）
    """
    with open(image_path, 'rb') as f:
        filename = os.path.basename(image_path)
        mime, _ = mimetypes.guess_type(filename)
        mime = mime or 'application/octet-stream'
        # (filename, fileobj, content_type)
        files = {'image': (filename, f, mime)}
        try:
            response = requests.post(POSE_SERVER_URL_SINGLE, files=files, timeout=timeout)
            response.raise_for_status()
            return response.json()  # 假设服务端返回json格式
        except Exception as e:
            print(f'姿态估计请求失败: {e}')
            return None

def get_pose_from_image_async(image_path, callback=None):
    """
    异步发送图片到姿态估计服务器，完成后调用回调函数。
    :param image_path: 图片文件路径
    :param callback: 回调函数，参数为结果
    """
    def task():
        result = get_pose_from_image(image_path)
        if callback:
            callback(result)
    thread = threading.Thread(target=task)
    thread.start()
    return thread

def send_images_and_get_result(image_paths, timeout=120):
    """
    批量发送图片到服务器，等待处理结果。
    :param image_paths: 图片路径列表
    :return: 服务器返回的json
    """
    try:
        if not image_paths:
            raise ValueError('image_paths 为空')
        # 使用 ExitStack 安全管理多个文件句柄，附带文件名与 MIME 类型
        with ExitStack() as stack:
            files_payload = []
            for p in image_paths:
                f = stack.enter_context(open(p, 'rb'))
                filename = os.path.basename(p)
                mime, _ = mimetypes.guess_type(filename)
                mime = mime or 'application/octet-stream'
                files_payload.append(('images', (filename, f, mime)))
            response = requests.post(POSE_SERVER_URL_SEQUENCE, files=files_payload, timeout=timeout)
            response.raise_for_status()
            data = response.json()
            # 打印服务端关键返回，便于排查
            if isinstance(data, dict) and data.get('success') is False:
                print(f"批量姿态估计返回错误: {data}")
            return data
    except Exception as e:
        print(f'批量姿态估计请求失败: {e}')
        return None


def stream_pose():
    url = "http://172.20.10.3:5000/open_external_video"
    payload = {
        "show_window": True,   # 远程运行建议关掉窗口
        "cutoff_hz": 6.0,       # 可根据需要调节滤波
        "output_fps": 10.0
    }

    with contextlib.closing(
        requests.post(url, json=payload, stream=True, timeout=None)
    ) as resp:
        resp.raise_for_status()
        print("开始接收姿态流...")
        for line in resp.iter_lines(decode_unicode=True):
            if not line:
                continue
            try:
                data = json.loads(line)
                print("[POSE STREAM]", data)
            except json.JSONDecodeError as e:
                print("[POSE STREAM] JSON 解析失败:", e)

if __name__ == "__main__":
    stream_pose()
