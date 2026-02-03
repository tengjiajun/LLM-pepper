'''
Author: shijie 245208483@qq.com
Date: 2025-09-18 11:14:50
LastEditors: shijie 245208483@qq.com
LastEditTime: 2025-09-18 16:14:38
FilePath: \naoqi-pose-retargeting-main\testMediaPipe.py
Description: 这是默认设置,请设置`customMade`, 打开koroFileHeader查看配置 进行设置: https://github.com/OBKoro1/koro1FileHeader/wiki/%E9%85%8D%E7%BD%AE
'''
import cv2
import mediapipe as mp
from utils.drawlandmarks import draw_landmarks, calc_bounding_rect, draw_bounding_rect

# 初始化 Pose 模块
mp_pose = mp.solutions.pose
pose = mp_pose.Pose()
mp_draw = mp.solutions.drawing_utils

cap = cv2.VideoCapture(0)

while cap.isOpened():
    ret, frame = cap.read()
    if not ret:
        break

    rgb_frame = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
    result = pose.process(rgb_frame)

    if result.pose_landmarks:
        # 使用自定义的关键点绘制函数
        frame = draw_landmarks(frame, result.pose_landmarks)
        
        # 可选：绘制边界框
        # brect = calc_bounding_rect(frame, result.pose_landmarks)
        # frame = draw_bounding_rect(True, frame, brect)

    cv2.imshow("Pose Estimation", frame)

    key = cv2.waitKey(1)
    if key == 27:  # ESC
        break

cap.release()
cv2.destroyAllWindows()
