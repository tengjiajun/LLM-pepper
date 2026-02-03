#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""
VLM机器人跟随系统快速启动脚本
检查依赖并启动系统
"""

import sys
import os

def check_dependencies():
    """检查必要依赖"""
    print("🔍 检查系统依赖...")
    
    missing_deps = []
    
    # 检查OpenCV
    try:
        import cv2
        print(f"✅ OpenCV: {cv2.__version__}")
    except ImportError:
        missing_deps.append("opencv-python")
        print("❌ OpenCV未安装")
    
    # 检查NumPy
    try:
        import numpy as np
        print(f"✅ NumPy: {np.__version__}")
    except ImportError:
        missing_deps.append("numpy")
        print("❌ NumPy未安装")
    
    # 检查Requests
    try:
        import requests
        print(f"✅ Requests: {requests.__version__}")
    except ImportError:
        missing_deps.append("requests")
        print("❌ Requests未安装")
    
    if missing_deps:
        print(f"\n❌ 缺少依赖: {', '.join(missing_deps)}")
        print("请运行以下命令安装:")
        print(f"pip install {' '.join(missing_deps)}")
        return False
    
    return True

def check_camera():
    """检查摄像头"""
    print("\n📷 检查摄像头...")
    try:
        import cv2
        cap = cv2.VideoCapture(0)
        if cap.isOpened():
            ret, frame = cap.read()
            if ret:
                h, w = frame.shape[:2]
                print(f"✅ 摄像头正常: {w}x{h}")
                cap.release()
                return True
            else:
                print("❌ 无法读取摄像头")
                cap.release()
                return False
        else:
            print("❌ 无法打开摄像头")
            return False
    except Exception as e:
        print(f"❌ 摄像头检测异常: {e}")
        return False

def check_api():
    """检查API配置"""
    print("\n🔑 检查API配置...")
    
    openai_key = os.getenv("OPENAI_API_KEY")
    hf_token = os.getenv("HF_API_TOKEN")
    
    if openai_key and openai_key not in ["", "your-api-key-here"]:
        print("✅ OpenAI API Key已配置")
        return "openai"
    elif hf_token and hf_token not in ["", "your-hf-token-here"]:
        print("✅ Hugging Face Token已配置")
        return "huggingface"
    else:
        print("⚠️  未配置API密钥")
        print("💡 提示: 系统将使用规则决策模式（功能有限）")
        print("📝 要使用完整VLM功能，请配置以下环境变量之一:")
        print("   Windows: set OPENAI_API_KEY=your-key-here")
        print("   Linux/Mac: export OPENAI_API_KEY=your-key-here")
        return "rules"

def main():
    """主函数"""
    print("🤖 VLM机器人跟随系统启动检查")
    print("=" * 60)
    
    # 检查依赖
    if not check_dependencies():
        print("\n❌ 依赖检查失败，无法启动系统")
        return False
    
    # 检查摄像头
    camera_ok = check_camera()
    if not camera_ok:
        print("⚠️  摄像头检查失败，但系统仍可启动（可能无法正常工作）")
    
    # 检查API
    api_mode = check_api()
    
    print(f"\n📊 系统状态:")
    print(f"   依赖: ✅ 完整")
    print(f"   摄像头: {'✅ 正常' if camera_ok else '❌ 异常'}")
    print(f"   VLM模式: {api_mode}")
    
    # 启动确认
    print(f"\n🚀 准备启动系统...")
    try:
        from demo import main as start_system
        print("✅ 主程序加载成功")
        print("=" * 60)
        print("📋 使用说明:")
        print("   - 在摄像头窗口中按 'q' 退出")
        print("   - 按 's' 保存动作日志")
        print("   - 按 'r' 重置系统状态")
        print("=" * 60)
        print("\n🎬 启动中...\n")
        
        # 启动主系统
        start_system()
        
    except ImportError as e:
        print(f"❌ 无法导入主程序: {e}")
        print("请确保demo.py文件存在且正确")
        return False
    except KeyboardInterrupt:
        print("\n⏹️  用户中断")
    except Exception as e:
        print(f"\n❌ 系统运行异常: {e}")
        return False
    
    print("👋 系统已退出")
    return True

if __name__ == "__main__":
    try:
        success = main()
        sys.exit(0 if success else 1)
    except KeyboardInterrupt:
        print("\n⏹️  启动被中断")
        sys.exit(1)