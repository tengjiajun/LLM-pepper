# LLM-pepper

基于LLM的pepper机器人自然语言动作微调

## 启动程序说明

- controller.py：控制端程序启动入口
- pepper.py：Pepper 机器人执行端启动入口
- server.py：通信控制端与执行端的服务端程序
- start_pose_server.py：姿态估计服务端启动入口（对应 naoqi-pose-retargeting/pose_analysis_server.py）

## 虚拟 Pepper（仿真）启动

本项目已加入最小适配层：通过环境变量切换真实 Pepper / qiBullet 仿真 Pepper，尽量不改原先动作控制逻辑。

1) 安装依赖（仿真端）

`pip install qibullet pybullet numpy`

1) 启动服务端

`python server.py`

1) 启动仿真 Pepper（新开终端）

PowerShell：

`$env:PEPPER_MODE="sim"; python pepper.py`

可选：

- `PEPPER_SIM_GUI=0` 关闭 GUI
- `PEPPER_SIM_GROUND=0` 不生成地面
