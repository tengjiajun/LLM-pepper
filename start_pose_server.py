#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""启动姿态估计服务端（包装入口）"""

from pathlib import Path
import sys

ROOT_DIR = Path(__file__).resolve().parent
POSE_SERVER_DIR = ROOT_DIR / "naoqi-pose-retargeting"
sys.path.insert(0, str(POSE_SERVER_DIR))

from pose_analysis_server import main


if __name__ == "__main__":
    main()
