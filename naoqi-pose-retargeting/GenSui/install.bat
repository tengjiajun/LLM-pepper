@echo off
REM VLM机器人跟随系统 Windows 安装脚本

echo 🤖 VLM机器人跟随系统安装程序
echo ================================

REM 检查Python版本
echo 🐍 检查Python环境...
python --version >nul 2>&1
if errorlevel 1 (
    echo ❌ Python未安装或不在PATH中
    echo 请安装Python 3.8+后重试
    pause
    exit /b 1
) else (
    for /f "tokens=*" %%i in ('python --version') do echo ✅ %%i
)

REM 检查conda环境
echo 🐍 检查Conda环境...
conda --version >nul 2>&1
if errorlevel 1 (
    echo ⚠️  Conda未安装，将使用系统Python环境
) else (
    echo ✅ Conda已安装
    
    REM 检查naoqi-pose环境
    conda env list | findstr "naoqi-pose" >nul
    if errorlevel 1 (
        echo ⚠️  naoqi-pose环境不存在，将使用当前环境
    ) else (
        echo ✅ naoqi-pose环境已存在
        echo 🔄 激活环境...
        call conda activate naoqi-pose
    )
)

REM 安装基础依赖
echo 📦 安装基础依赖包...
python -m pip install --upgrade pip

echo 🔄 安装OpenCV...
pip install opencv-python

echo 🔄 安装Requests...
pip install requests

echo 🔄 安装NumPy...
pip install numpy

echo 🔄 安装其他依赖...
pip install Pillow matplotlib

REM 检查摄像头
echo 📷 检查摄像头访问...
python -c "import cv2; cap=cv2.VideoCapture(0); print('✅ 摄像头访问正常' if cap.isOpened() else '❌ 无法访问摄像头'); cap.release() if cap.isOpened() else None" 2>nul
if errorlevel 1 (
    echo ⚠️  摄像头测试失败，请检查摄像头连接和权限
)

REM 检查API配置
echo 🔑 检查API配置...
if defined OPENAI_API_KEY (
    echo ✅ OpenAI API Key已配置
) else if defined HF_API_TOKEN (
    echo ✅ Hugging Face API Token已配置
) else (
    echo ⚠️  未检测到API配置，系统将使用规则决策模式
    echo 📝 配置说明：
    echo    OpenAI: set OPENAI_API_KEY=your-key-here
    echo    HuggingFace: set HF_API_TOKEN=your-token-here
)

REM 创建配置模板
echo 📝 创建配置模板...
(
echo # VLM机器人跟随系统配置模板
echo # 复制此文件为config.py并修改相应参数
echo.
echo # API配置
echo OPENAI_API_KEY = "your-openai-api-key-here"
echo HF_API_TOKEN = "your-hf-token-here"
echo.
echo # 系统配置
echo USE_OPENAI = True  # True=OpenAI, False=HuggingFace
echo.
echo # 摄像头配置
echo CAMERA_INDEX = 0
echo CAMERA_WIDTH = 640
echo CAMERA_HEIGHT = 480
echo.
echo # 机器人参数
echo MAX_SPEED = 0.5
echo SAFE_DISTANCE = 1.5
echo.
echo # Pepper配置
echo PEPPER_IP = "192.168.1.100"
echo PEPPER_PORT = 9559
) > config_template.py

echo ✅ 配置模板已创建: config_template.py

REM 创建Windows启动脚本
echo 🚀 创建启动脚本...
(
echo @echo off
echo echo 🤖 启动VLM机器人跟随系统...
echo echo.
echo.
echo REM 检查conda环境
echo conda info ^> nul 2^>^&1
echo if errorlevel 1 ^(
echo     echo ⚠️  Conda未安装，使用系统Python
echo ^) else ^(
echo     echo 🔄 激活naoqi-pose环境...
echo     call conda activate naoqi-pose
echo ^)
echo.
echo REM 检查API配置
echo if not defined OPENAI_API_KEY ^(
echo     if not defined HF_API_TOKEN ^(
echo         echo ⚠️  未配置API密钥，将使用规则决策模式
echo     ^)
echo ^)
echo.
echo REM 启动系统
echo echo 🚀 启动系统...
echo python demo.py
echo.
echo pause
) > start_system.bat

echo ✅ 启动脚本已创建: start_system.bat

REM 创建测试脚本
echo 🧪 创建测试脚本...
(
echo import sys
echo import os
echo.
echo def test_imports^(^):
echo     print^("🔍 测试依赖导入..."^)
echo     try:
echo         import cv2
echo         print^(f"✅ OpenCV: {cv2.__version__}"^)
echo     except ImportError:
echo         print^("❌ OpenCV导入失败"^)
echo         return False
echo     return True
echo.
echo def test_camera^(^):
echo     print^("📷 测试摄像头..."^)
echo     try:
echo         import cv2
echo         cap = cv2.VideoCapture^(0^)
echo         if cap.isOpened^(^):
echo             print^("✅ 摄像头正常"^)
echo             cap.release^(^)
echo             return True
echo         else:
echo             print^("❌ 无法打开摄像头"^)
echo             return False
echo     except Exception as e:
echo         print^(f"❌ 摄像头测试异常: {e}"^)
echo         return False
echo.
echo if __name__ == "__main__":
echo     print^("🧪 VLM机器人跟随系统测试"^)
echo     if test_imports^(^) and test_camera^(^):
echo         print^("✅ 所有测试通过"^)
echo     else:
echo         print^("❌ 部分测试失败"^)
) > test_system.py

echo ✅ 测试脚本已创建: test_system.py

REM 运行测试
echo.
echo 🧪 运行系统测试...
python test_system.py

REM 完成安装
echo.
echo 🎉 安装完成！
echo =================
echo 📁 生成的文件:
echo    - demo.py ^(主程序^)
echo    - README.md ^(使用说明^)
echo    - requirements_vlm.txt ^(依赖列表^)
echo    - config_template.py ^(配置模板^)
echo    - start_system.bat ^(启动脚本^)
echo    - test_system.py ^(测试脚本^)
echo.
echo 🚀 启动方法:
echo    方法1: python demo.py
echo    方法2: start_system.bat
echo.
echo 📖 使用说明请查看: README.md

pause