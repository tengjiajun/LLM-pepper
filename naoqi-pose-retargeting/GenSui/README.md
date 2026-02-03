# 基于VLM的机器人跟随系统

## 项目描述

本项目基于笔记本前置摄像头和Vision-Language Model (VLM)实现机器人跟随功能。系统通过普通RGB摄像头捕获图像，使用VLM进行场景理解和决策，生成机器人控制信号。当前版本将控制信号输出到控制台模拟机器人行为，并提供了适配到Pepper机器人的完整方案。

## 系统架构

### 核心模块

1. **感知模块 (VLMPerception)**
   - 使用OpenCV捕获摄像头图像
   - 调用VLM API进行场景分析
   - 识别目标人物位置和距离
   - 检测导航障碍物

2. **决策模块 (DecisionMaker)**
   - 基于感知结果生成动作指令
   - 支持VLM智能决策和规则后备方案
   - 动作类型：前进、转向、停止、搜索

3. **控制信号生成模块 (ControlSignalGenerator)**
   - 将决策转换为具体控制信号
   - 当前输出到控制台模拟
   - 提供Pepper机器人适配接口

### 技术特点

- **单目视觉**: 基于透视和物体大小估计距离
- **VLM驱动**: 支持OpenAI GPT-4 Vision和开源LLaVA
- **实时处理**: 可调帧率，平衡性能和响应
- **安全机制**: 障碍物检测和安全距离控制
- **模块化设计**: 易于扩展和适配其他机器人

## 安装和配置

### 环境要求

- Python 3.8+
- 笔记本前置摄像头
- （可选）OpenAI API Key 或 Hugging Face API Token

### 依赖安装

```bash
# 激活conda环境
conda activate naoqi-pose

# 安装基本依赖
pip install opencv-python requests numpy

# 如果需要matplotlib（可选，用于可视化）
pip install matplotlib
```

### API配置

#### OpenAI GPT-4 Vision（推荐）

1. 获取OpenAI API Key：https://platform.openai.com/api-keys
2. 设置环境变量：
   ```bash
   # Windows
   set OPENAI_API_KEY=your-actual-api-key-here
   
   # Linux/macOS
   export OPENAI_API_KEY=your-actual-api-key-here
   ```

#### Hugging Face LLaVA（开源替代）

1. 获取HF Token：https://huggingface.co/settings/tokens
2. 设置环境变量：
   ```bash
   # Windows
   set HF_API_TOKEN=your-hf-token-here
   
   # Linux/macOS
   export HF_API_TOKEN=your-hf-token-here
   ```

### 配置文件修改

在 `demo.py` 中的 `Config` 类里修改以下参数：

```python
class Config:
    # VLM选择
    USE_OPENAI = True  # True=OpenAI, False=HuggingFace
    
    # 摄像头配置
    CAMERA_INDEX = 0  # 通常0是前置摄像头
    CAMERA_WIDTH = 640
    CAMERA_HEIGHT = 480
    
    # 机器人参数
    MAX_SPEED = 0.5      # 最大移动速度 (m/s)
    SAFE_DISTANCE = 1.5  # 安全跟随距离 (m)
    
    # Pepper连接（适配时使用）
    PEPPER_IP = "192.168.1.100"  # 替换为实际IP
```

## 使用方法

### 1. 基本运行

```bash
cd GenSui
python demo.py
```

### 2. 交互控制

运行后，在摄像头窗口中：
- 按 `q` 键：退出系统
- 按 `s` 键：保存动作日志
- 按 `p` 键：连接Pepper机器人（需要适配）
- 按 `r` 键：重置系统状态

### 3. 控制台输出示例

```
================================================================
[14:30:15.123] 控制信号输出
================================================================
🚶 前进控制: 速度 0.20 m/s, 距离 0.30 m
📝 决策原因: 目标在中心，距离2.1m，缓慢前进
⏱️  执行时长: 1.5 秒
================================================================
```

## 适配到Pepper机器人

### 1. 安装NAOqi SDK

```bash
# 下载并安装NAOqi Python SDK 2.5
# 注意：NAOqi需要Python 2.7，建议使用虚拟环境
conda create -n pepper python=2.7
conda activate pepper
pip install naoqi-python
```

### 2. 修改代码

在 `ControlSignalGenerator` 类中启用Pepper控制：

```python
def connect_pepper(self, ip: str = None, port: int = None) -> bool:
    """连接Pepper机器人"""
    try:
        from naoqi import ALProxy
        
        ip = ip or Config.PEPPER_IP
        port = port or Config.PEPPER_PORT
        
        # 创建运动代理
        self.motion_proxy = ALProxy("ALMotion", ip, port)
        self.motion_proxy.wakeUp()
        
        self.is_pepper_connected = True
        self.logger.info(f"成功连接到Pepper机器人: {ip}:{port}")
        return True
        
    except Exception as e:
        self.logger.error(f"Pepper连接失败: {e}")
        return False

def _execute_pepper_action(self, action: str, params: Dict) -> bool:
    """执行Pepper机器人控制"""
    try:
        if action == 'move':
            distance = params.get('distance', 0)
            speed = params.get('speed', 0.3)
            self.motion_proxy.moveTo(distance, 0, 0, speed)
            
        elif action == 'turn':
            angle = params.get('angle', 0)
            speed = params.get('speed', 0.2)
            self.motion_proxy.moveTo(0, 0, angle, speed)
            
        elif action == 'stop':
            self.motion_proxy.stopMove()
            
        return True
        
    except Exception as e:
        self.logger.error(f"Pepper控制执行失败: {e}")
        return False
```

### 3. 摄像头切换

将OpenCV摄像头替换为Pepper眼部摄像头：

```python
def _init_pepper_camera(self):
    """初始化Pepper摄像头"""
    try:
        from naoqi import ALProxy
        
        self.video_proxy = ALProxy("ALVideoDevice", Config.PEPPER_IP, Config.PEPPER_PORT)
        
        # 订阅摄像头
        self.camera_name = self.video_proxy.subscribeCamera(
            "python_camera", 0, 2, 11, 10  # 顶部摄像头，640x480，RGB
        )
        
        self.logger.info("Pepper摄像头初始化成功")
        return True
        
    except Exception as e:
        self.logger.error(f"Pepper摄像头初始化失败: {e}")
        return False

def capture_pepper_frame(self):
    """从Pepper摄像头捕获图像"""
    try:
        image_data = self.video_proxy.getImageRemote(self.camera_name)
        
        # 转换为numpy数组
        width, height = image_data[0], image_data[1]
        image_array = np.frombuffer(image_data[6], dtype=np.uint8)
        image = image_array.reshape(height, width, 3)
        
        return image
        
    except Exception as e:
        self.logger.error(f"Pepper图像捕获失败: {e}")
        return None
```

## 性能优化

### 1. 降低API调用频率

```python
# 在Config类中调整
FRAME_INTERVAL = 0.2  # 每0.2秒处理一帧（5fps）
```

### 2. 使用本地VLM

推荐使用本地部署的LLaVA：

```bash
# 安装transformers
pip install transformers torch

# 下载LLaVA模型（需要GPU）
from transformers import LlavaNextProcessor, LlavaNextForConditionalGeneration

processor = LlavaNextProcessor.from_pretrained("llava-hf/llava-v1.6-mistral-7b-hf")
model = LlavaNextForConditionalGeneration.from_pretrained("llava-hf/llava-v1.6-mistral-7b-hf")
```

### 3. 缓存优化

```python
# 缓存相似帧的分析结果
def should_analyze_frame(self, current_frame, last_frame, threshold=0.1):
    """判断是否需要重新分析帧"""
    if last_frame is None:
        return True
    
    # 计算帧差异
    diff = cv2.absdiff(current_frame, last_frame)
    diff_ratio = np.mean(diff) / 255.0
    
    return diff_ratio > threshold
```

## 安全注意事项

### 1. 距离控制

```python
# 在DecisionMaker中添加安全检查
def _safety_check(self, decision: Dict) -> Dict:
    """安全检查，防止碰撞"""
    if decision['action'] == 'move':
        # 限制最大移动距离
        max_distance = 0.5  # 单次最大移动0.5米
        if decision['params']['distance'] > max_distance:
            decision['params']['distance'] = max_distance
    
    return decision
```

### 2. 紧急停止

```python
# 添加紧急停止机制
def emergency_stop(self):
    """紧急停止"""
    if self.is_pepper_connected:
        self.motion_proxy.stopMove()
    
    self.logger.warning("执行紧急停止")
```

## 故障排除

### 1. 摄像头问题

```bash
# 测试摄像头
python -c "import cv2; cap=cv2.VideoCapture(0); print('Camera OK' if cap.isOpened() else 'Camera Error')"
```

### 2. API问题

```bash
# 测试OpenAI API
curl -H "Authorization: Bearer $OPENAI_API_KEY" https://api.openai.com/v1/models
```

### 3. 常见错误

- **导入错误**: 确保安装了所有依赖 `pip install opencv-python requests numpy`
- **API配置**: 检查环境变量是否正确设置
- **摄像头权限**: 确保应用有摄像头访问权限
- **网络问题**: 检查网络连接和防火墙设置

## 扩展功能

### 1. 多人跟踪

修改VLM提示，指定特定目标：

```python
self.perception_prompt = """
分析图像中穿红色衣服的人，忽略其他人...
"""
```

### 2. 语音交互

```python
# 添加语音识别（Pepper适配时）
def init_speech_recognition(self):
    from naoqi import ALProxy
    self.speech_proxy = ALProxy("ALSpeechRecognition", Config.PEPPER_IP, Config.PEPPER_PORT)
    self.speech_proxy.setLanguage("Chinese")
```

### 3. 路径规划

```python
# 添加路径记录和重播
class PathPlanner:
    def __init__(self):
        self.path_history = []
    
    def record_position(self, x, y, theta):
        self.path_history.append((time.time(), x, y, theta))
    
    def replay_path(self):
        # 重播记录的路径
        pass
```

## 许可证

本项目基于原始naoqi-pose-retargeting项目开发，遵循相应的开源许可证。

## 贡献

欢迎提交Issue和Pull Request来改进这个项目。

---

**注意**: 本系统当前处于原型阶段，实际部署到生产环境前请进行充分测试，确保安全性和可靠性。