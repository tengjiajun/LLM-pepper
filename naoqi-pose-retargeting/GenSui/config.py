"""
VLM机器人跟随系统配置文件
请根据您的环境修改以下配置
"""

import os

# =============================================================================
# API配置 - 请选择其中一种方式配置
# =============================================================================

# 方法1: 直接在此文件中配置（不推荐，有安全风险）
OPENAI_API_KEY = "your-openai-api-key-here"
HF_API_TOKEN = "your-hf-token-here"

# 方法2: 从环境变量读取（推荐）
# OPENAI_API_KEY = os.getenv("OPENAI_API_KEY", "")
# HF_API_TOKEN = os.getenv("HF_API_TOKEN", "")

# 选择VLM服务提供商
USE_OPENAI = True  # True=OpenAI GPT-4 Vision, False=Hugging Face LLaVA

# =============================================================================
# 摄像头配置
# =============================================================================

CAMERA_INDEX = 0        # 摄像头索引（通常0是默认/前置摄像头）
CAMERA_WIDTH = 640      # 图像宽度像素
CAMERA_HEIGHT = 480     # 图像高度像素
CAMERA_FPS = 10         # 摄像头帧率

# =============================================================================
# 系统性能配置
# =============================================================================

FRAME_INTERVAL = 0.1    # 帧处理间隔（秒）- 值越小处理越快但消耗越多
VLM_TIMEOUT = 10        # VLM API超时时间（秒）
ENABLE_DISPLAY = True   # 是否显示摄像头窗口

# =============================================================================
# 机器人控制参数
# =============================================================================

MAX_SPEED = 0.5         # 最大移动速度 (m/s)
MAX_TURN_SPEED = 0.3    # 最大转向速度 (rad/s)
SAFE_DISTANCE = 1.5     # 安全跟随距离 (m)
MIN_DISTANCE = 0.8      # 最小跟随距离 (m)
MAX_DISTANCE = 3.0      # 最大跟随距离 (m)

# =============================================================================
# Pepper机器人配置（适配时使用）
# =============================================================================

PEPPER_IP = "192.168.1.100"    # Pepper机器人IP地址
PEPPER_PORT = 9559             # NAOqi SDK端口
ENABLE_PEPPER = False          # 是否启用Pepper连接

# =============================================================================
# 日志和调试配置
# =============================================================================

LOG_LEVEL = "INFO"      # 日志级别：DEBUG, INFO, WARNING, ERROR
ENABLE_FILE_LOG = True  # 是否启用文件日志
LOG_FORMAT = "%(asctime)s - %(name)s - %(levelname)s - %(message)s"

# 性能监控
SHOW_FPS = True         # 是否显示FPS
SHOW_STATUS = True      # 是否显示状态信息

# =============================================================================
# VLM提示配置（高级用户）
# =============================================================================

# 感知提示模板
PERCEPTION_PROMPT = """
分析这张图片进行机器人导航：
1. 检测图像中的人（目标跟随对象）
2. 估计人的位置（左侧/中心/右侧）和距离（米）
3. 识别可能的障碍物
4. 返回JSON格式结果

请基于人体在图像中的大小估计距离，成年人身高约1.7米作为参考。
"""

# 决策提示模板  
DECISION_PROMPT = """
基于感知信息为机器人跟随任务决定动作：
- 目标在中心且距离适当：缓慢前进
- 目标偏左/右：转向目标
- 检测到障碍物：停止
- 未检测到目标：搜索模式
"""

# =============================================================================
# 缓存和优化配置
# =============================================================================

ENABLE_CACHING = True   # 启用结果缓存（减少API调用）
CACHE_DURATION = 2.0    # 缓存有效期（秒）
MAX_CACHE_SIZE = 100    # 最大缓存条目数

# 帧差异检测（避免处理相似帧）
ENABLE_FRAME_DIFF = True    # 启用帧差异检测
FRAME_DIFF_THRESHOLD = 0.1  # 帧差异阈值（0-1）

# =============================================================================
# 安全和限制配置
# =============================================================================

# 动作限制
MAX_MOVE_DISTANCE = 1.0     # 单次最大移动距离 (m)
MAX_TURN_ANGLE = 1.57       # 单次最大转向角度 (rad, π/2 = 90度)
ACTION_COOLDOWN = 0.5       # 动作间最小间隔 (s)

# 紧急停止条件
EMERGENCY_STOP_DISTANCE = 0.3   # 紧急停止距离 (m)
OBSTACLE_STOP_KEYWORDS = ["wall", "obstacle", "barrier", "墙", "障碍"]

# =============================================================================
# 实验性功能配置
# =============================================================================

# 多人跟踪
ENABLE_MULTI_PERSON = False     # 启用多人检测
TARGET_PERSON_DESCRIPTION = ""  # 目标人物描述（如"穿红色衣服的人"）

# 路径记录
ENABLE_PATH_RECORDING = True    # 启用路径记录
MAX_PATH_HISTORY = 1000         # 最大路径点数

# 语音反馈（Pepper适配时）
ENABLE_VOICE_FEEDBACK = False   # 启用语音反馈
VOICE_LANGUAGE = "Chinese"      # 语音语言

# =============================================================================
# 开发者选项
# =============================================================================

DEBUG_MODE = False          # 调试模式（显示详细信息）
SAVE_DEBUG_IMAGES = False   # 保存调试图像
DEBUG_IMAGE_DIR = "debug_images"  # 调试图像保存目录

# 性能分析
ENABLE_PROFILING = False    # 启用性能分析
PROFILE_OUTPUT = "profile_results.txt"  # 性能分析输出文件

# 模拟模式（无摄像头测试）
SIMULATION_MODE = False     # 启用模拟模式
SIMULATION_IMAGE_PATH = "test_image.jpg"  # 模拟图像路径

# =============================================================================
# 验证配置函数
# =============================================================================

def validate_config():
    """验证配置是否有效"""
    errors = []
    warnings = []
    
    # 检查API配置
    if USE_OPENAI:
        if not OPENAI_API_KEY or OPENAI_API_KEY == "your-openai-api-key-here":
            warnings.append("OpenAI API Key未配置，将使用规则决策")
    else:
        if not HF_API_TOKEN or HF_API_TOKEN == "your-hf-token-here":
            warnings.append("Hugging Face Token未配置，将使用规则决策")
    
    # 检查摄像头配置
    if CAMERA_INDEX < 0:
        errors.append("摄像头索引不能为负数")
    
    if CAMERA_WIDTH <= 0 or CAMERA_HEIGHT <= 0:
        errors.append("摄像头分辨率必须大于0")
    
    # 检查机器人参数
    if MAX_SPEED <= 0:
        errors.append("最大速度必须大于0")
    
    if SAFE_DISTANCE <= 0:
        errors.append("安全距离必须大于0")
    
    if MIN_DISTANCE >= MAX_DISTANCE:
        errors.append("最小距离必须小于最大距离")
    
    # 检查Pepper配置
    if ENABLE_PEPPER:
        if not PEPPER_IP:
            errors.append("启用Pepper时必须配置IP地址")
        
        if PEPPER_PORT <= 0 or PEPPER_PORT > 65535:
            errors.append("Pepper端口必须在1-65535范围内")
    
    return errors, warnings

if __name__ == "__main__":
    # 配置验证
    errors, warnings = validate_config()
    
    print("🔧 配置验证结果:")
    print("=" * 50)
    
    if errors:
        print("❌ 配置错误:")
        for error in errors:
            print(f"   - {error}")
    
    if warnings:
        print("⚠️  配置警告:")
        for warning in warnings:
            print(f"   - {warning}")
    
    if not errors and not warnings:
        print("✅ 配置验证通过")
    elif not errors:
        print("⚠️  配置可用但有警告")
    else:
        print("❌ 配置有错误，请修正后重试")