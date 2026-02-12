import json
import socket
import threading
from pathlib import Path
import sys
import os
import argparse

ROOT_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT_DIR))

from llm_module import FUNCTION_ACTIONS, LLMRouter

class PepperServer:
    def __init__(self, host="localhost", port=5566, api_key="sk-32e369888c6a48f1918d0f2e0b3488a1", base_url="https://dashscope.aliyuncs.com/compatible-mode/v1"):
        self.host = host
        self.port = port
        self.server_socket = None
        self.running_event = threading.Event()
        self.llm_router = LLMRouter(api_key=api_key, base_url=base_url, function_actions=FUNCTION_ACTIONS)
        self.json_cache = self.llm_router.json_cache  # 缓存 API 处理结果
        # 定义关键词列表，用于过滤与小朋友的交流
        self.ignore_keywords = self.llm_router.ignore_keywords  # 可根据需要扩展

    def process_command(self, raw_text):
        return self.llm_router.process_command(raw_text)

    def start(self):
        """启动服务器"""
        try:
            self.server_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            # Allow quick restart on the same port.
            try:
                self.server_socket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
            except Exception:
                pass
            self.server_socket.bind((self.host, self.port))
            self.server_socket.listen(1)
            self.running_event.set()
            print(f"Pepper控制服务器已启动，监听在 {self.host}:{self.port}")

            while self.running_event.is_set():
                try:
                    self.server_socket.settimeout(1.0)  # 设置超时以检查 running_event
                    client_socket, address = self.server_socket.accept()
                    print(f"收到来自 {address} 的连接")
                    
                    # 接收数据
                    data = client_socket.recv(1024).decode('utf-8')
                    print(f"收到命令: {data}")
                    
                    # 处理命令并获取 API 响应
                    response = self.process_command(data)
                    
                    # 发送响应给客户端（序列化为 JSON 字符串）
                    client_socket.send(json.dumps(response, ensure_ascii=False).encode('utf-8'))
                    client_socket.close()
                    
                except socket.timeout:
                    continue
                except Exception as e:
                    print(f"处理客户端连接时出错: {str(e)}")
                    
        except Exception as e:
            print(f"服务器启动失败: {str(e)}")
            if isinstance(e, OSError) and getattr(e, "winerror", None) == 10048:
                print(
                    "端口被占用：可能你已经运行过一个同端口的控制服务器，或其他程序占用了该端口。\n"
                    "解决方法：\n"
                    "1) 关闭已运行的脚本窗口/进程；或\n"
                    "2) 换端口启动：python ShenFenDaiRu0528.py --port 5567；或\n"
                    "3) 查占用进程：netstat -ano | findstr :5566，然后 taskkill /PID <pid> /F"
                )
        finally:
            self.stop()

    def stop(self):
        """停止服务器"""
        self.running_event.clear()
        if self.server_socket:
            try:
                self.server_socket.close()
            except Exception:
                pass
            self.server_socket = None
            print("Pepper控制服务器已停止")
            print(f"最终缓存内容: {json.dumps(self.json_cache, ensure_ascii=False, indent=2)}")

def main():
    parser = argparse.ArgumentParser(description="Pepper 控制服务器（LLM Router）")
    parser.add_argument("--host", default=os.getenv("PEPPER_CTRL_HOST", "localhost"))
    parser.add_argument("--port", type=int, default=int(os.getenv("PEPPER_CTRL_PORT", "5566")))
    args = parser.parse_args()

    # 创建并启动 Pepper 服务器
    pepper_server = PepperServer(host=args.host, port=args.port)
    server_thread = threading.Thread(target=pepper_server.start)
    server_thread.start()

    # 保持程序运行，直到用户输入 'exit' 或 Ctrl+C
    try:
        while True:
            user_input = input("输入 'exit' 退出程序: ")
            if user_input.lower() == "exit":
                pepper_server.stop()
                break
            response = pepper_server.process_command(user_input)
            print(f"处理控制台输入结果: {response}")
    except KeyboardInterrupt:
        print("收到中断信号，正在停止服务器...")
        pepper_server.stop()
    finally:
        server_thread.join()  # 等待线程结束

if __name__ == "__main__":
    main()