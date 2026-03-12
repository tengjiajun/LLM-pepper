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

## Unitree（宇树/宇数）机器人仿真：科研建议

如果后续大概率没有 Unitree 真机、但导师要求用 Unitree 做仿真，建议选 **WSL2(Ubuntu) + ROS2 + Gazebo** 作为科研底座：

- 可复现、开源、论文/实验最常用
- 方便接入导航/建图/多传感器（即使你当前只用到移动指令）
- 你现有工程的控制链路（controller → server → 执行端）可以不改，只要写一个“Unitree 执行端适配器”把 `move` 等指令翻译为 `/cmd_vel`

本仓库已新增一个最小 Unitree 执行端骨架，先用 **mock 后端** 在 Windows 上跑通闭环；之后你把它放到 WSL2 的 ROS2 环境运行即可发布 `/cmd_vel`。

### H1（人形）特别说明

H1 属于人形机器人：科研实验往往不仅是底盘速度，还会涉及上肢/全身关节控制。基于你当前需求“走路 + 上半身简单动作，并尽量复用 Pepper 的 intent”，推荐的选型是：

- **Windows 原生优先**：更建议用 **Isaac Sim** 或 **MuJoCo** 作为仿真（人形/关节控制更常见），然后写一个 Python 适配层把本仓库的 intent 翻译成“关节目标/控制器指令”。
- **如果你们未来要强 ROS2 生态（导航/传感器/系统集成）**：再考虑 WSL2(Ubuntu)+ROS2+Gazebo，但对人形的上肢/全身控制链路通常需要额外控制器配置。

当前仓库的 Unitree 适配器里：

- `move`：可用 mock 打印或 ROS2 `/cmd_vel` 发布（用于“走路/转向”最小闭环）
- `body/head/active_1/active_2`：先做了“接收+解析+打印”的占位，确保 Pepper 的 intent 能无改动到达 H1 仿真端；你们定仿真平台后再替换为真实关节控制实现。

## LLM 动作评估/编辑（暂不含 token/Transformer）

如果你现在主要想完成图里的 **评估器(LLM)** 与“自然语言→结构化文本”部分，本仓库新增了一个最小的 LLM 动作编辑协议与调用封装：

- 协议定义：`llm_module/motion_schema.py`（MotionEdit / MotionJudge）
- LLM 封装：`llm_module/motion_editor.py`（MotionLLM.propose_edit / MotionLLM.judge）
- Demo：`tools/motion_llm_demo.py`

运行 demo（需要 OpenAI-compatible 接口；默认示例适配通义千问 compatible-mode）：

PowerShell：

`$env:LLM_API_KEY="<你的key>"; $env:LLM_BASE_URL="https://dashscope.aliyuncs.com/compatible-mode/v1"; python tools/motion_llm_demo.py`

说明：推荐把视频/关节序列先用算法提取成 `motion_summary`（关节范围、速度、超限指标等），再交给 LLM 产出结构化 edit，保证实验可复现、可记录。

## MuJoCo 仿真（最小查看器）

仓库内提供了一个最小 MuJoCo 查看器，用于验证“模型能加载 + 仿真能跑”。

安装依赖（已在本仓库虚拟环境中使用 pip 安装）：

`pip install mujoco numpy glfw`

运行（需要你自己提供 H1 的 MJCF/XML 模型路径，本仓库不内置 H1 模型文件）：

`python tools/mujoco_sim_view.py --model path/to/model.xml`

### 一键跑通（占位人形模型）

如果你暂时还没有 H1 的模型文件，但想先把“MuJoCo 在电脑上能跑起来”验证掉，可以直接运行：

`run_mujoco_demo.bat`

它会加载仓库内置的占位模型 `mujoco_models/simple_humanoid.xml` 打开仿真窗口。注意：这不是 H1 的真实模型，只用于先打通仿真链路。

### 运行 Unitree H1（MuJoCo Menagerie 模型）

如果你已把 `mujoco_menagerie/unitree_h1` 拷贝进仓库（包含 `scene.xml`/`h1.xml`/`assets/`），可以直接运行：

`run_unitree_h1_mujoco.bat`

它会加载 `mujoco_menagerie/unitree_h1/scene.xml` 并重置到 `home` keyframe。

如果你运行可视化窗口时感觉“卡住/没弹窗”，可以先做 headless 加载自检：

`run_unitree_h1_mujoco_smoke.bat`

### 1) Windows 上先跑通（mock）

1) 启动服务端：

`python server.py`

1) 启动 Unitree 执行端（mock，仅打印 cmd_vel）：

`python unitree.py --backend mock`

1) 启动控制端（键盘/语音/LLM）：

`python controller.py`

此时在控制端按键（如 F1 开启移动 + WASD/QE）或通过语音/LLM 触发 `forward/left_spin_rotate/...`，终端会看到 `[unitree][mock] cmd_vel ...`，说明链路已打通。

### 2) 连接 ROS2/Gazebo（后续科研仿真）

当你在 WSL2(Ubuntu) 里装好 ROS2 与 Unitree 的 Gazebo 仿真后，用同一份代码运行：

`UNITREE_BACKEND=ros2 python unitree.py --backend ros2 --server-ip <Windows主机IP> --server-port 5556 --cmd-vel-topic /cmd_vel`

说明：

- `--server-ip` 需要填写 Windows 上运行 `server.py` 的 IP（WSL2 通常不能直接用 127.0.0.1 指向 Windows 服务，取决于你的转发配置）。
- Unitree 仿真侧只要订阅 `/cmd_vel` 并驱动底盘即可完成最小实验闭环；上肢/姿态模仿可后续再扩展。
