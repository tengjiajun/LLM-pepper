"""
Navigation Client for SLAM Server
Provides HTTP-based navigation control and map video streaming
"""
import requests
import time
from typing import Optional, Dict, Any


class NavigationClient:
    """Client for SLAM navigation server"""
    
    def __init__(self, host: str = "172.168.10.3", port: int = 5000):
        """
        Initialize navigation client
        
        Args:
            host: SLAM server IP address
            port: SLAM server port
        """
        self.host = host
        self.port = port
        self.base_url = f"http://{host}:{port}"
        
        # Map video streaming state
        self.map_frame = None
        self.map_streaming = False
        self.stream_thread = None
        self._stop_stream = False
        
        # Connection state
        self.connected = False
        self._check_connection()
    
    def _check_connection(self):
        """Check if server is reachable"""
        try:
            response = requests.get(f"{self.base_url}/health", timeout=2)
            self.connected = response.status_code == 200
            print(f"[Navigation] Server connection: {'OK' if self.connected else 'Failed'}")
        except Exception as e:
            self.connected = False
            print(f"[Navigation] Server unreachable: {e}")
    
    def goto(self, goal: str) -> str:
        """发送导航命令。

        返回值分类:
          'start' : 已开始执行 (202 或 status=start/running)
          'ok'    : 已接受 (200)
          'busy'  : 已有任务在执行 (409)
          'error' : 其他错误
        """
        try:
            url = f"{self.base_url}/navigateto"
            payload = {"goal": goal}
            print(f"[Navigation] POST /navigateto goal={goal}")
            resp = requests.post(url, json=payload, timeout=5)
            code = resp.status_code
            txt = resp.text
            js: Optional[Dict[str, Any]] = None
            try:
                js = resp.json()
            except Exception:
                js = None

            if code == 409:
                msg = js.get('message') if isinstance(js, dict) else txt
                print(f"[Navigation] busy (409): {msg}")
                return 'busy'
            if code == 202:
                if isinstance(js, dict):
                    st = str(js.get('status', '')).lower()
                    msg = js.get('message', '')
                    if st in ('start', 'started', 'running'):
                        print(f"[Navigation] started (202): {msg}")
                        return 'start'
                print(f"[Navigation] started (202 raw): {txt}")
                return 'start'
            if code == 200:
                print(f"[Navigation] accepted (200): {txt}")
                return 'ok'
            print(f"[Navigation] goto error {code}: {txt}")
            return 'error'
        except Exception as e:
            print(f"[Navigation] goto exception: {e}")
            self.connected = False
            return 'error'
    
    def goto_and_wait(self,
                      goal: str,
                      poll_interval: float = 1.0,
                      max_wait: float = 600.0,
                      retry_busy: bool = True) -> bool:
        """发送导航命令并阻塞等待完成。

        完成判定：/status 返回 status=='end' 且 result=='success'
        忙判定：goto 返回 'busy' (409)。
        """
        print(f"[Navigation] goto_and_wait start goal={goal}")
        phase = self.goto(goal)
        if phase == 'error':
            print("[Navigation] initial goto error")
            return False
        if phase == 'busy':
            if not retry_busy:
                print("[Navigation] busy & no retry")
                return False
            print("[Navigation] busy: 等待当前任务结束再重试")
            if not self._wait_until_free(poll_interval, max_wait):
                print("[Navigation] 等待当前任务结束超时")
                return False
            phase = self.goto(goal)
            if phase not in ('start', 'ok'):
                print("[Navigation] 重试仍失败")
                return False
        # 已开始或已接受 -> 等待成功
        return self._wait_success(poll_interval, max_wait)

    def _wait_until_free(self, poll_interval: float, max_wait: float) -> bool:
        """等待直到服务器不再处于 start/running/navigating 状态 (出现 end 或 idle 或 OK)。"""
        start_t = time.time()
        while time.time() - start_t < max_wait:
            st = self.get_status()
            if st:
                if isinstance(st, str):
                    if st.strip().upper() == 'OK':
                        return True
                elif isinstance(st, dict):
                    s = str(st.get('status', '')).lower()
                    if s in ('end', 'idle'):
                        return True
            time.sleep(poll_interval)
        return False

    def _wait_success(self, poll_interval: float, max_wait: float) -> bool:
        """轮询等待成功完成，容错多种服务端返回格式。"""
        start_t = time.time()
        polls = 0
        while time.time() - start_t < max_wait:
            polls += 1
            st = self.get_status()
            if st:
                # 1) 纯文本 OK
                if isinstance(st, str):
                    if st.strip().upper() == 'OK':
                        print(f"[Navigation] success (plain OK) after {polls} polls")
                        return True
                # 2) JSON 对象
                elif isinstance(st, dict):
                    status_val = str(st.get('status', '')).strip()
                    code_val = str(st.get('code', '')).strip()
                    state_val = str(st.get('state', '')).strip()
                    result_val = str(st.get('result', '')).strip()
                    message_val = str(st.get('message', '')).strip()

                    # 任一字段为 OK
                    for v in (status_val, code_val, state_val, result_val):
                        if v.upper() == 'OK':
                            print(f"[Navigation] success (field OK) after {polls} polls")
                            return True

                    # 明确失败信号
                    if result_val.upper() in {'FAIL', 'ERROR'} or code_val.upper() in {'FAIL', 'ERROR'}:
                        print(f"[Navigation] failure reported: result={result_val}, code={code_val}")
                        return False
                    if any(tok in message_val for tok in {'失败', '错误', '取消', '中断'}):
                        print(f"[Navigation] failure message: {message_val}")
                        return False

                    # end 阶段：有 success/ok 视为成功；无 result 也按成功处理（兼容部分实现）
                    if status_val.lower() == 'end':
                        if result_val.lower() in {'success', 'ok'}:
                            print(f"[Navigation] success (end+{result_val}) after {polls} polls")
                            return True
                        if not result_val:
                            print(f"[Navigation] success (end, no result) after {polls} polls")
                            return True
            time.sleep(poll_interval)
        print(f"[Navigation] timeout waiting success ({time.time()-start_t:.1f}s)")
        return False

    # 地图流暂未实现，保留占位
    def start_map_stream(self, window_name: str = "SLAM Map"):
        print("[Navigation] map stream unavailable")
    def stop_map_stream(self):
        print("[Navigation] map stream unavailable")
    
    def get_status(self) -> Optional[object]:
        """
        Get current navigation status from server
        
        Returns:
            Status dict, plain string (e.g. 'OK'), or None if failed
        """
        try:
            response = requests.get(f"{self.base_url}/status", timeout=2)
            if response.status_code == 200:
                try:
                    return response.json()
                except ValueError:
                    return response.text.strip()
            return None
        except Exception as e:
            print(f"[Navigation] Status query error: {e}")
            return None
    
    def stop(self) -> bool:
        """
        Send stop command to halt navigation
        
        Returns:
            True if command accepted
        """
        try:
            response = requests.post(f"{self.base_url}/stop", timeout=2)
            return response.status_code == 200
        except Exception as e:
            print(f"[Navigation] Stop command error: {e}")
            return False
    
    def close(self):
        """Clean up resources"""
        print("[Navigation] Client closed")


# Global instance for controller module
_nav_client: Optional[NavigationClient] = None


def get_nav_client(host: str = "172.168.10.3", port: int = 5000) -> NavigationClient:
    """
    Get or create global navigation client instance
    
    Args:
        host: SLAM server IP
        port: SLAM server port
    
    Returns:
        NavigationClient instance
    """
    global _nav_client
    if _nav_client is None:
        _nav_client = NavigationClient(host, port)
    return _nav_client


# Example usage
if __name__ == "__main__":
    # Create client (adjust host if needed)
    client = NavigationClient("172.20.10.3", 5000)

    allowed = {"A","HOME"}

    print("Navigation interactive (immediate execute)")
    print("Commands:")
    print("  A/B/C/HOME  (可空格或逗号分隔批量) -> 立即按顺序执行")
    print("  stop       -> 发送停止当前导航")
    print("  quit/exit  -> 退出程序")

    while True:
        try:
            line = input("> ").strip()
        except (EOFError, KeyboardInterrupt):
            print("\nExit.")
            break

        if not line:
            continue

        cmd = line.strip().upper()

        if cmd in ("Q", "QUIT", "EXIT"):
            break
        elif cmd == "STOP":
            if client.stop():
                print("Stop sent (200).")
            else:
                print("Stop failed.")
        else:
            # 立即执行：将逗号替换为空格，支持批量顺序执行
            tokens = [t for t in cmd.replace(',', ' ').split() if t]
            goals = []
            for t in tokens:
                if t in allowed:
                    goals.append(t)
                else:
                    print(f"Unsupported goal: {t} (allowed: A,B,C,HOME)")
            if goals:
                print(f"Executing: {goals}")
                for g in goals:
                    print(f"-> Navigating to {g} ...")
                    ok = client.goto_and_wait(g, poll_interval=1.0, max_wait=600)
                    print(f"   Result: {'OK' if ok else 'FAILED'}")
                    time.sleep(0.3)

    client.close()
