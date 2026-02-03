# 单张图片姿态估计器

## 功能说明

这个模块可以输入一张图片，完成人体姿态估计并输出关节角度，包含以下功能：

- 使用 MediaPipe 进行人体姿态检测
- 计算 9 个关节角度：LShoulderPitch, LShoulderRoll, LElbowYaw, LElbowRoll, RShoulderPitch, RShoulderRoll, RElbowYaw, RElbowRoll, HipPitch
- 输出弧度和角度两种格式
- 检查关节角度是否在 Pepper 机器人的安全范围内

## 文件说明

### 1. `pose_estimator.py` - 主要的姿态估计器类
包含完整的 `PoseEstimator` 类，提供以下功能：
- 加载和处理图片
- 进行姿态检测
- 计算关节角度
- 安全检查
- 结果输出

### 2. `simple_example.py` - 简单使用示例
提供快速使用的示例代码。

## 使用方法

### 方法一：直接运行姿态估计器
```bash
python pose_estimator.py image.jpg
```

### 方法二：使用简化示例
```bash
python simple_example.py image.jpg
```

### 方法三：在代码中调用
```python
from pose_estimator import PoseEstimator

# 创建估计器
estimator = PoseEstimator()

# 进行姿态估计
result = estimator.estimate_pose("your_image.jpg")

# 获取角度
if result is not None:
    angles_rad = result['angles']['angles_rad']  # 弧度
    angles_deg = result['angles']['angles_deg']  # 角度
    print("angles =", angles_rad)
```

## 输出格式

程序会输出以下信息：

1. **关节角度（弧度）**: 与原程序格式一致的数组
2. **关节角度（度数）**: 更易读的角度格式
3. **安全检查**: 检查是否在 Pepper 机器人的关节限制范围内

示例输出：
```
============================================================
图片: test_image.jpg
============================================================
关节角度 (弧度):
[-0.123, 0.456, -0.789, 1.234, 0.567, -0.890, 0.345, -0.678, 0.123]

关节角度 (度数):
  LShoulderPitch :   -7.05°
  LShoulderRoll  :   26.13°
  LElbowYaw      :  -45.22°
  RShoulderPitch :   32.78°
  ...

安全检查: ✓ 所有关节在安全范围内

============================================================
angles = [LShoulderPitch,LShoulderRoll, LElbowYaw, LElbowRoll, RShoulderPitch,RShoulderRoll, RElbowYaw, RElbowRoll, HipPitch]
弧度: [-0.123, 0.456, -0.789, 1.234, 0.567, -0.890, 0.345, -0.678, 0.123]
角度: [-7.05, 26.13, -45.22, 70.70, 32.48, -51.01, 19.77, -38.85, 7.05]
```

## 关节说明

输出的 9 个关节角度对应：
1. **LShoulderPitch**: 左肩俯仰角
2. **LShoulderRoll**: 左肩横滚角
3. **LElbowYaw**: 左肘偏航角
4. **LElbowRoll**: 左肘横滚角
5. **RShoulderPitch**: 右肩俯仰角
6. **RShoulderRoll**: 右肩横滚角
7. **RElbowYaw**: 右肘偏航角
8. **RElbowRoll**: 右肘横滚角
9. **HipPitch**: 髋部俯仰角

## 依赖库

确保已安装以下依赖：
- opencv-python
- numpy
- mediapipe
- utils 模块（来自原项目）

## 注意事项

1. 输入图片应包含清晰的人体姿态
2. 人体应尽量完整可见
3. 光线条件良好有助于提高检测精度
4. 支持常见图片格式：jpg, png, bmp 等