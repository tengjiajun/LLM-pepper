#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""
单张图片姿态估计器
输入一张图片，输出人体关节角度（弧度转角度）
"""

import cv2 as cv
import numpy as np
import mediapipe as mp
import math
from utils import KeypointsToAngles

class PoseEstimator:
    """
    姿态估计器类
    用于处理单张图片并计算人体关节角度
    """
    
    def __init__(self, 
                 model_complexity=1,
                 min_detection_confidence=0.5,
                 min_tracking_confidence=0.5):
        """
        初始化姿态估计器
        
        Args:
            model_complexity: 模型复杂度 (0,1,2)
            min_detection_confidence: 最小检测置信度
            min_tracking_confidence: 最小追踪置信度
        """
        # 初始化MediaPipe Pose
        self.mp_pose = mp.solutions.pose
        self.pose = self.mp_pose.Pose(
            model_complexity=model_complexity,
            enable_segmentation=False,
            min_detection_confidence=min_detection_confidence,
            min_tracking_confidence=min_tracking_confidence,
        )
        
        # 初始化角度计算器
        self.keypointsToAngles = KeypointsToAngles()
        
        # Pepper机器人关节限制（弧度）
        self.joint_limits = {
            'LShoulderPitch': [-2.0857, 2.0857],
            'RShoulderPitch': [-2.0857, 2.0857],
            'LShoulderRoll':  [0.0087, 1.5620],
            'RShoulderRoll':  [-1.5620, -0.0087],
            'LElbowYaw':      [-2.0857, 2.0857],
            'RElbowYaw':      [-2.0857, 2.0857],
            'LElbowRoll':     [-1.5620, -0.0087],
            'RElbowRoll':     [0.0087, 1.5620],
            'HeadPitch':      [-0.52, 0.52],      # 约 -30° ~ 30°
            'HipPitch':       [-0.6, 0.0]       # 约 -35° ~ 0°
        }
    
    def load_image(self, image_path):
        """
        加载图片文件
        
        Args:
            image_path: 图片文件路径
            
        Returns:
            numpy.ndarray: 加载的图片，如果失败返回None
        """
        try:
            image = cv.imread(image_path)
            if image is None:
                print(f"错误: 无法加载图片 {image_path}")
                return None
            return image
        except Exception as e:
            print(f"加载图片时出错: {e}")
            return None
    
    def process_image(self, image):
        """
        处理图片并检测姿态
        
        Args:
            image: 输入图片
            
        Returns:
            tuple: (是否检测成功, MediaPipe检测结果)
        """
        if image is None:
            return False, None
            
        # 转换颜色空间
        rgb_image = cv.cvtColor(image, cv.COLOR_BGR2RGB)
        
        # 进行姿态检测
        results = self.pose.process(rgb_image)
        
        # 检查是否检测到姿态
        if results.pose_world_landmarks is None:
            print("未检测到人体姿态")
            return False, None
            
        return True, results
    
    def extract_keypoints(self, landmarks):
        """
        提取关键点坐标
        
        Args:
            landmarks: MediaPipe的landmarks结果
            
        Returns:
            numpy.ndarray: 关键点坐标数组
        """
        p = []
        for landmark in landmarks.landmark:
            p.append([landmark.x, landmark.y, landmark.z])
        return np.array(p)
    
    def calculate_angles(self, landmarks):
        """
        计算关节角度
        
        Args:
            landmarks: MediaPipe的pose_world_landmarks
            
        Returns:
            dict: 包含角度信息的字典
        """
        # 提取关键点坐标
        p = self.extract_keypoints(landmarks)
        
        # 计算虚拟关键点
        pNeck = (0.5 * (np.array(p[11]) + np.array(p[12]))).tolist()    # 脖子中点
        pMidHip = (0.5 * (np.array(p[23]) + np.array(p[24]))).tolist()  # 髋部中点
        
        # 计算各关节角度
        LShoulderPitch, LShoulderRoll = self.keypointsToAngles.obtain_LShoulderPitchRoll_angles(
            pNeck, p[11], p[13], pMidHip)
        
        RShoulderPitch, RShoulderRoll = self.keypointsToAngles.obtain_RShoulderPitchRoll_angles(
            pNeck, p[12], p[14], pMidHip)
        
        LElbowYaw, LElbowRoll = self.keypointsToAngles.obtain_LElbowYawRoll_angle(
            pNeck, p[11], p[13], p[15])
        
        RElbowYaw, RElbowRoll = self.keypointsToAngles.obtain_RElbowYawRoll_angle(
            pNeck, p[12], p[14], p[16])
        
        HipPitch = self.keypointsToAngles.obtain_HipPitch_angles(pMidHip, pNeck)
        HeadPitch = self.keypointsToAngles.obtain_HeadPitch_angle(pNeck, p[0])
        
        # 弧度转角度
        angles_rad = [
            LShoulderPitch, LShoulderRoll, LElbowYaw, LElbowRoll,
            RShoulderPitch, RShoulderRoll, RElbowYaw, RElbowRoll,
            HeadPitch, HipPitch
        ]
        
        angles_deg = [math.degrees(angle) for angle in angles_rad]
        
        # 构建结果字典
        angle_names = [
            "LShoulderPitch", "LShoulderRoll", "LElbowYaw", "LElbowRoll",
            "RShoulderPitch", "RShoulderRoll", "RElbowYaw", "RElbowRoll",
            "HeadPitch", "HipPitch"
        ]
        
        result = {
            'angles_rad': angles_rad,
            'angles_deg': angles_deg,
            'angle_dict_rad': dict(zip(angle_names, angles_rad)),
            'angle_dict_deg': dict(zip(angle_names, angles_deg))
        }
        
        return result
    
    def check_limits(self, angles_rad):
        """
        检查关节角度是否在安全范围内
        
        Args:
            angles_rad: 弧度制的关节角度列表
            
        Returns:
            dict: 检查结果
        """
        angle_names = ["LShoulderPitch", "LShoulderRoll", "LElbowYaw", "LElbowRoll", 
                       "RShoulderPitch", "RShoulderRoll", "RElbowYaw", "RElbowRoll", "HeadPitch", "HipPitch"]
        
        limit_check = {}
        within_limits = True
        
        for i, (name, angle) in enumerate(zip(angle_names, angles_rad)):
            limits = self.joint_limits[name]
            is_safe = limits[0] <= angle <= limits[1]
            limit_check[name] = {
                'angle': angle,
                'limits': limits,
                'safe': is_safe
            }
            if not is_safe:
                within_limits = False
        
        return {
            'all_safe': within_limits,
            'details': limit_check
        }
    
    def estimate_pose(self, image_path):
        """
        完整的姿态估计流程
        
        Args:
            image_path: 图片路径
            
        Returns:
            dict: 估计结果
        """
        # 加载图片
        image = self.load_image(image_path)
        if image is None:
            return None
        
        # 处理图片
        success, results = self.process_image(image)
        if not success:
            return None
        
        # 计算角度
        angle_result = self.calculate_angles(results.pose_world_landmarks)
        
        # 检查限制
        limit_result = self.check_limits(angle_result['angles_rad'])
        
        # 合并结果
        final_result = {
            'success': True,
            'image_path': image_path,
            'angles': angle_result,
            'safety_check': limit_result
        }
        
        return final_result
    
    def print_results(self, result):
        """
        打印结果
        
        Args:
            result: estimate_pose的返回结果
        """
        if result is None:
            print("姿态估计失败")
            return
        
        print("=" * 60)
        print(f"图片: {result['image_path']}")
        print("=" * 60)
        
        # 打印角度（弧度）
        print("关节角度 (弧度):")
        print(result['angles']['angles_rad'])
        
        # 打印角度（度数）
        print("\n关节角度 (度数):")
        for name, angle in result['angles']['angle_dict_deg'].items():
            print(f"  {name:15}: {angle:8.2f}°")
        
        # 打印安全检查
        print(f"\n安全检查: {'✓ 所有关节在安全范围内' if result['safety_check']['all_safe'] else '⚠ 部分关节超出安全范围'}")
        
        if not result['safety_check']['all_safe']:
            print("\n超出限制的关节:")
            for name, check in result['safety_check']['details'].items():
                if not check['safe']:
                    print(f"  {name}: {math.degrees(check['angle']):.2f}° (限制: {math.degrees(check['limits'][0]):.2f}° ~ {math.degrees(check['limits'][1]):.2f}°)")


def main():
    """
    主函数 - 示例用法
    """
    import sys
    
    if len(sys.argv) != 2:
        print("用法: python pose_estimator.py <图片路径>")
        print("示例: python pose_estimator.py image.jpg")
        return
    
    image_path = sys.argv[1]
    
    # 创建姿态估计器
    estimator = PoseEstimator()
    
    # 进行姿态估计
    result = estimator.estimate_pose(image_path)
    
    # 打印结果
    estimator.print_results(result)
    
    # 如果需要只打印angles数组（与原程序格式一致）
    if result is not None:
        print("\n" + "="*60)
        print("angles = [LShoulderPitch,LShoulderRoll, LElbowYaw, LElbowRoll, RShoulderPitch,RShoulderRoll, RElbowYaw, RElbowRoll, HipPitch]")
        print("弧度:", result['angles']['angles_rad'])
        print("角度:", result['angles']['angles_deg'])


if __name__ == '__main__':
    main()
