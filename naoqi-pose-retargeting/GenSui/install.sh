#!/bin/bash
# VLM机器人跟随系统安装脚本
# 适用于Windows PowerShell、Linux Bash和macOS

echo "🤖 VLM机器人跟随系统安装程序"
echo "================================"

# 检测操作系统
if [[ "$OSTYPE" == "msys" ]] || [[ "$OSTYPE" == "win32" ]]; then
    OS="windows"
elif [[ "$OSTYPE" == "linux-gnu"* ]]; then
    OS="linux"
elif [[ "$OSTYPE" == "darwin"* ]]; then
    OS="macos"
else
    OS="unknown"
fi

echo "📱 检测到操作系统: $OS"

# 检查Python版本
echo "🐍 检查Python环境..."
python_version=$(python --version 2>&1)
if [[ $? -eq 0 ]]; then
    echo "✅ $python_version"
else
    echo "❌ Python未安装或不在PATH中"
    exit 1
fi

# 检查conda环境
echo "🐍 检查Conda环境..."
if command -v conda &> /dev/null; then
    echo "✅ Conda已安装"
    
    # 检查naoqi-pose环境是否存在
    if conda env list | grep -q "naoqi-pose"; then
        echo "✅ naoqi-pose环境已存在"
        echo "🔄 激活环境..."
        eval "$(conda shell.bash hook)"
        conda activate naoqi-pose
    else
        echo "⚠️  naoqi-pose环境不存在，将使用当前环境"
    fi
else
    echo "⚠️  Conda未安装，将使用系统Python环境"
fi

# 安装基础依赖
echo "📦 安装基础依赖包..."
pip install --upgrade pip

echo "🔄 安装OpenCV..."
pip install opencv-python

echo "🔄 安装Requests..."
pip install requests

echo "🔄 安装NumPy..."
pip install numpy

echo "🔄 安装其他依赖..."
pip install Pillow matplotlib

# 检查摄像头
echo "📷 检查摄像头访问..."
python -c "
import cv2
import sys
try:
    cap = cv2.VideoCapture(0)
    if cap.isOpened():
        print('✅ 摄像头访问正常')
        cap.release()
    else:
        print('❌ 无法访问摄像头')
        sys.exit(1)
except Exception as e:
    print(f'❌ 摄像头测试失败: {e}')
    sys.exit(1)
"

if [[ $? -ne 0 ]]; then
    echo "⚠️  摄像头测试失败，请检查摄像头连接和权限"
fi

# 检查API配置
echo "🔑 检查API配置..."
if [[ -n "$OPENAI_API_KEY" ]]; then
    echo "✅ OpenAI API Key已配置"
elif [[ -n "$HF_API_TOKEN" ]]; then
    echo "✅ Hugging Face API Token已配置"
else
    echo "⚠️  未检测到API配置，系统将使用规则决策模式"
    echo "📝 配置说明："
    echo "   OpenAI: export OPENAI_API_KEY=your-key-here"
    echo "   HuggingFace: export HF_API_TOKEN=your-token-here"
fi

# 创建配置模板
echo "📝 创建配置模板..."
cat > config_template.py << 'EOF'
"""
VLM机器人跟随系统配置模板
复制此文件为config.py并修改相应参数
"""

# API配置
OPENAI_API_KEY = "your-openai-api-key-here"  # 从环境变量获取：os.getenv("OPENAI_API_KEY")
HF_API_TOKEN = "your-hf-token-here"          # 从环境变量获取：os.getenv("HF_API_TOKEN")

# 系统配置
USE_OPENAI = True  # True=OpenAI GPT-4 Vision, False=Hugging Face LLaVA

# 摄像头配置
CAMERA_INDEX = 0        # 摄像头索引（通常0是默认摄像头）
CAMERA_WIDTH = 640      # 图像宽度
CAMERA_HEIGHT = 480     # 图像高度
CAMERA_FPS = 10         # 摄像头帧率

# 处理配置
FRAME_INTERVAL = 0.1    # 帧处理间隔（秒）
VLM_TIMEOUT = 10        # VLM API超时时间（秒）

# 机器人控制参数
MAX_SPEED = 0.5         # 最大移动速度 (m/s)
MAX_TURN_SPEED = 0.3    # 最大转向速度 (rad/s)
SAFE_DISTANCE = 1.5     # 安全跟随距离 (m)

# Pepper机器人配置（适配时使用）
PEPPER_IP = "192.168.1.100"    # Pepper机器人IP地址
PEPPER_PORT = 9559             # NAOqi端口

# 日志配置
LOG_LEVEL = "INFO"      # 日志级别：DEBUG, INFO, WARNING, ERROR
ENABLE_FILE_LOG = True  # 是否启用文件日志

# 性能优化
ENABLE_CACHING = True   # 启用结果缓存
CACHE_DURATION = 2.0    # 缓存有效期（秒）
MAX_CACHE_SIZE = 100    # 最大缓存条目数
EOF

echo "✅ 配置模板已创建: config_template.py"

# 创建启动脚本
echo "🚀 创建启动脚本..."

if [[ "$OS" == "windows" ]]; then
    cat > start_system.bat << 'EOF'
@echo off
echo 🤖 启动VLM机器人跟随系统...
echo.

REM 检查conda环境
conda info > nul 2>&1
if errorlevel 1 (
    echo ⚠️  Conda未安装，使用系统Python
) else (
    echo 🔄 激活naoqi-pose环境...
    call conda activate naoqi-pose
)

REM 检查API配置
if not defined OPENAI_API_KEY (
    if not defined HF_API_TOKEN (
        echo ⚠️  未配置API密钥，将使用规则决策模式
    )
)

REM 启动系统
echo 🚀 启动系统...
python demo.py

pause
EOF
    echo "✅ Windows启动脚本已创建: start_system.bat"
fi

cat > start_system.sh << 'EOF'
#!/bin/bash
echo "🤖 启动VLM机器人跟随系统..."
echo

# 激活conda环境（如果存在）
if command -v conda &> /dev/null; then
    if conda env list | grep -q "naoqi-pose"; then
        echo "🔄 激活naoqi-pose环境..."
        eval "$(conda shell.bash hook)"
        conda activate naoqi-pose
    fi
fi

# 检查API配置
if [[ -z "$OPENAI_API_KEY" ]] && [[ -z "$HF_API_TOKEN" ]]; then
    echo "⚠️  未配置API密钥，将使用规则决策模式"
fi

# 启动系统
echo "🚀 启动系统..."
python demo.py
EOF

chmod +x start_system.sh
echo "✅ Linux/macOS启动脚本已创建: start_system.sh"

# 创建测试脚本
echo "🧪 创建测试脚本..."
cat > test_system.py << 'EOF'
#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
VLM机器人跟随系统测试脚本
"""

import sys
import os

def test_imports():
    """测试依赖导入"""
    print("🔍 测试依赖导入...")
    
    try:
        import cv2
        print(f"✅ OpenCV: {cv2.__version__}")
    except ImportError as e:
        print(f"❌ OpenCV导入失败: {e}")
        return False
    
    try:
        import numpy as np
        print(f"✅ NumPy: {np.__version__}")
    except ImportError as e:
        print(f"❌ NumPy导入失败: {e}")
        return False
    
    try:
        import requests
        print(f"✅ Requests: {requests.__version__}")
    except ImportError as e:
        print(f"❌ Requests导入失败: {e}")
        return False
    
    return True

def test_camera():
    """测试摄像头"""
    print("\n📷 测试摄像头...")
    
    try:
        import cv2
        cap = cv2.VideoCapture(0)
        
        if cap.isOpened():
            ret, frame = cap.read()
            if ret:
                height, width = frame.shape[:2]
                print(f"✅ 摄像头正常: {width}x{height}")
                cap.release()
                return True
            else:
                print("❌ 无法读取摄像头图像")
                cap.release()
                return False
        else:
            print("❌ 无法打开摄像头")
            return False
            
    except Exception as e:
        print(f"❌ 摄像头测试异常: {e}")
        return False

def test_api_config():
    """测试API配置"""
    print("\n🔑 测试API配置...")
    
    openai_key = os.getenv("OPENAI_API_KEY")
    hf_token = os.getenv("HF_API_TOKEN")
    
    if openai_key and openai_key != "your-api-key-here":
        print("✅ OpenAI API Key已配置")
        return True
    elif hf_token and hf_token != "your-hf-token-here":
        print("✅ Hugging Face Token已配置")
        return True
    else:
        print("⚠️  未配置API密钥，将使用规则决策模式")
        return False

def main():
    """主测试函数"""
    print("🧪 VLM机器人跟随系统测试")
    print("=" * 50)
    
    tests_passed = 0
    total_tests = 3
    
    # 测试依赖导入
    if test_imports():
        tests_passed += 1
    
    # 测试摄像头
    if test_camera():
        tests_passed += 1
    
    # 测试API配置
    if test_api_config():
        tests_passed += 1
    
    print(f"\n📊 测试结果: {tests_passed}/{total_tests} 通过")
    
    if tests_passed == total_tests:
        print("✅ 所有测试通过，系统可以运行")
        return True
    elif tests_passed >= 2:
        print("⚠️  部分测试通过，系统可以基本运行")
        return True
    else:
        print("❌ 关键测试失败，请检查安装")
        return False

if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1)
EOF

echo "✅ 测试脚本已创建: test_system.py"

# 运行测试
echo ""
echo "🧪 运行系统测试..."
python test_system.py

# 完成安装
echo ""
echo "🎉 安装完成！"
echo "=" * 50
echo "📁 生成的文件:"
echo "   - demo.py (主程序)"
echo "   - README.md (使用说明)"
echo "   - requirements_vlm.txt (依赖列表)"
echo "   - config_template.py (配置模板)"
echo "   - test_system.py (测试脚本)"
if [[ "$OS" == "windows" ]]; then
    echo "   - start_system.bat (Windows启动脚本)"
fi
echo "   - start_system.sh (Linux/macOS启动脚本)"
echo ""
echo "🚀 启动方法:"
echo "   方法1: python demo.py"
if [[ "$OS" == "windows" ]]; then
    echo "   方法2: start_system.bat"
fi
echo "   方法3: ./start_system.sh"
echo ""
echo "📖 使用说明请查看: README.md"
echo "🔧 配置参考请查看: config_template.py"