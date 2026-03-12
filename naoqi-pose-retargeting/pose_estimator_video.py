#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""
视频姿态估计器
输入一段视频，以每秒10次的频率输出人体关节角度（弧度转角度）
"""

import cv2 as cv
import numpy as np
import mediapipe as mp
import math
import time
import os
import json
from utils import KeypointsToAngles

class VideoPoseEstimator:
    """
    视频姿态估计器类
    用于处理视频并以每秒10次的频率计算人体关节角度
    """
    
    def __init__(self, 
                 model_complexity=1,
                 min_detection_confidence=0.5,
                 min_tracking_confidence=0.5):
        """  
        初始化视频姿态估计器
        
        Args:
            model_complexity: 模型复杂度 (0,1,2)
            min_detection_confidence: 最小检测置信度
            min_tracking_confidence: 最小追踪置信度
        """
        # 初始化MediaPipe Pose
        self.mp_pose = mp.solutions.pose
        self.mp_drawing = mp.solutions.drawing_utils
        self.mp_drawing_styles = mp.solutions.drawing_styles
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
            'HipPitch':       [-1.0385, 1.0385]
        }
    
    def load_video(self, video_path):
        """
        加载视频文件
        
        Args:
            video_path: 视频文件路径
            
        Returns:
            cv2.VideoCapture: 视频捕获对象，如果失败返回None
        """
        try:
            cap = cv.VideoCapture(video_path)
            if not cap.isOpened():
                print(f"错误: 无法打开视频文件 {video_path}")
                return None
            return cap
        except Exception as e:
            print(f"加载视频时出错: {e}")
            return None
    
    def process_image(self, image):
        """
        处理单帧图片并检测姿态
        
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

    def serialize_landmarks_2d(self, landmarks):
        """
        序列化2D关键点（归一化坐标）
        """
        if landmarks is None:
            return []
        result = []
        for lm in landmarks.landmark:
            result.append({
                'x': float(lm.x),
                'y': float(lm.y),
                'z': float(lm.z),
                'visibility': float(getattr(lm, 'visibility', 0.0))
            })
        return result

    def serialize_landmarks_3d(self, world_landmarks):
        """
        序列化3D world关键点
        """
        if world_landmarks is None:
            return []
        result = []
        for lm in world_landmarks.landmark:
            result.append({
                'x': float(lm.x),
                'y': float(lm.y),
                'z': float(lm.z),
                'visibility': float(getattr(lm, 'visibility', 0.0))
            })
        return result
    
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
        
        # 弧度转角度
        angles_rad = [LShoulderPitch, LShoulderRoll, LElbowYaw, LElbowRoll, 
                      RShoulderPitch, RShoulderRoll, RElbowYaw, RElbowRoll, HipPitch]
        
        angles_deg = [math.degrees(angle) for angle in angles_rad]
        
        # 构建结果字典
        angle_names = ["LShoulderPitch", "LShoulderRoll", "LElbowYaw", "LElbowRoll", 
                       "RShoulderPitch", "RShoulderRoll", "RElbowYaw", "RElbowRoll", "HipPitch"]
        
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
                       "RShoulderPitch", "RShoulderRoll", "RElbowYaw", "RElbowRoll", "HipPitch"]
        
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
    
    def process_video(self, video_path, callback=None, target_fps=10, save_skeleton_video=False, skeleton_output_path=None):
        """
        处理视频并以指定频率输出姿态分析结果，可选导出骨架视频

        Args:
            video_path: 视频文件路径
            callback: 可选的回调函数，用于处理每次的姿态结果
                     回调函数格式: callback(frame_number, timestamp, result)
            target_fps: 目标处理频率，默认每秒10次
            save_skeleton_video: 是否导出骨架视频
            skeleton_output_path: 骨架视频输出路径

        Returns:
            list: 所有处理帧的姿态分析结果列表
        """
        cap = self.load_video(video_path)
        if cap is None:
            return None

        results_list = []
        frame_number = 0
        frame_interval = 1.0 / target_fps

        total_frames = int(cap.get(cv.CAP_PROP_FRAME_COUNT))
        video_fps = cap.get(cv.CAP_PROP_FPS)
        frame_w = int(cap.get(cv.CAP_PROP_FRAME_WIDTH))
        frame_h = int(cap.get(cv.CAP_PROP_FRAME_HEIGHT))
        duration = total_frames / video_fps if video_fps > 0 else 0

        print(f"视频信息:")
        print(f"  文件路径: {video_path}")
        print(f"  总帧数: {total_frames}")
        print(f"  视频FPS: {video_fps:.2f}")
        print(f"  视频时长: {duration:.2f}秒")
        print(f"  处理频率: {target_fps}Hz (每{frame_interval*1000:.0f}ms一次)")
        if save_skeleton_video:
            print(f"  骨架视频导出: 开启")
        print("=" * 60)

        writer = None
        if save_skeleton_video:
            if not skeleton_output_path:
                skeleton_output_path = os.path.splitext(video_path)[0] + "_skeleton.mp4"
            out_fps = target_fps if target_fps > 0 else (video_fps if video_fps > 0 else 10)
            fourcc = cv.VideoWriter_fourcc(*"mp4v")
            writer = cv.VideoWriter(skeleton_output_path, fourcc, out_fps, (frame_w, frame_h))
            if not writer.isOpened():
                print(f"警告: 无法创建骨架视频文件 {skeleton_output_path}，将继续只输出角度数据")
                writer = None

        start_time = time.time()
        next_process_time = 0
        processed_count = 0

        try:
            while True:
                ret, frame = cap.read()
                if not ret:
                    break

                current_video_time = frame_number / video_fps if video_fps > 0 else 0

                if current_video_time >= next_process_time:
                    processed_count += 1
                    success, pose_results = self.process_image(frame)

                    if success:
                        angle_result = self.calculate_angles(pose_results.pose_world_landmarks)
                        limit_result = self.check_limits(angle_result['angles_rad'])
                        landmarks_2d = self.serialize_landmarks_2d(pose_results.pose_landmarks)
                        landmarks_3d = self.serialize_landmarks_3d(pose_results.pose_world_landmarks)
                        visibility_values = [p['visibility'] for p in landmarks_2d]
                        mean_visibility = float(sum(visibility_values) / len(visibility_values)) if visibility_values else 0.0
                        frame_result = {
                            'success': True,
                            'frame_number': frame_number,
                            'video_timestamp': current_video_time,
                            'process_timestamp': time.time() - start_time,
                            'image_w': int(frame.shape[1]),
                            'image_h': int(frame.shape[0]),
                            'pose_landmarks2d': landmarks_2d,
                            'pose_world_landmarks3d': landmarks_3d,
                            'quality': {
                                'mean_visibility': mean_visibility,
                                'landmark_count_2d': len(landmarks_2d),
                                'landmark_count_3d': len(landmarks_3d)
                            },
                            'angles': angle_result,
                            'safety_check': limit_result
                        }
                        results_list.append(frame_result)

                        angles_str = [f'{x:.1f}' for x in angle_result['angles_deg']]
                        safety_status = "✓" if limit_result['all_safe'] else "⚠"
                        print(f"第{processed_count:3d}次 | 帧{frame_number:4d} | {current_video_time:6.2f}s | {safety_status} | 角度: {angles_str}")

                        if callback:
                            callback(frame_number, current_video_time, frame_result)
                    else:
                        frame_result = {
                            'success': False,
                            'frame_number': frame_number,
                            'video_timestamp': current_video_time,
                            'process_timestamp': time.time() - start_time,
                            'image_w': int(frame.shape[1]),
                            'image_h': int(frame.shape[0]),
                            'pose_landmarks2d': [],
                            'pose_world_landmarks3d': [],
                            'quality': {
                                'mean_visibility': 0.0,
                                'landmark_count_2d': 0,
                                'landmark_count_3d': 0
                            },
                            'message': '未检测到人体姿态'
                        }
                        results_list.append(frame_result)
                        print(f"第{processed_count:3d}次 | 帧{frame_number:4d} | {current_video_time:6.2f}s | ✗ | 未检测到姿态")

                    if writer is not None:
                        draw_frame = frame.copy()
                        if success and pose_results and pose_results.pose_landmarks:
                            self.mp_drawing.draw_landmarks(
                                draw_frame,
                                pose_results.pose_landmarks,
                                self.mp_pose.POSE_CONNECTIONS,
                                landmark_drawing_spec=self.mp_drawing_styles.get_default_pose_landmarks_style(),
                            )
                        status_text = "POSE: OK" if success else "POSE: MISS"
                        cv.putText(draw_frame, f"t={current_video_time:.2f}s", (20, 30), cv.FONT_HERSHEY_SIMPLEX, 0.8, (0, 255, 0), 2)
                        cv.putText(draw_frame, status_text, (20, 65), cv.FONT_HERSHEY_SIMPLEX, 0.8, (0, 255, 0) if success else (0, 0, 255), 2)
                        writer.write(draw_frame)

                    next_process_time += frame_interval

                frame_number += 1

                if frame_number % 100 == 0:
                    time.sleep(0.001)

        finally:
            cap.release()
            if writer is not None:
                writer.release()

        processing_time = time.time() - start_time
        successful_count = len([r for r in results_list if r['success']])

        print("=" * 60)
        print(f"处理完成:")
        print(f"  总处理时间: {processing_time:.2f}秒")
        print(f"  处理次数: {len(results_list)}")
        print(f"  成功检测: {successful_count}")
        print(f"  失败次数: {len(results_list) - successful_count}")
        print(f"  实际处理频率: {len(results_list)/processing_time:.2f}Hz")
        print(f"  成功率: {successful_count/len(results_list)*100:.1f}%" if results_list else "0%")
        if writer is not None and skeleton_output_path:
            print(f"  骨架视频已保存: {skeleton_output_path}")

        return results_list
    
    def save_results_to_json(self, results, output_path):
        """
        保存结果到JSON文件
        
        Args:
            results: process_video的返回结果
            output_path: 输出文件路径
        """
        try:
            with open(output_path, 'w', encoding='utf-8') as f:
                json.dump(results, f, indent=2, ensure_ascii=False)
            print(f"结果已保存到: {output_path}")
        except Exception as e:
            print(f"保存文件时出错: {e}")


def main():
    """
    主函数 - 视频姿态估计
    """
    import sys
    
    if len(sys.argv) < 2:
        print("用法: python pose_estimator_video.py <视频路径> [输出频率] [--save-video]")
        print("参数:")
        print("  视频路径: 支持的视频格式 (.mp4, .avi, .mov, .mkv, .wmv, .flv, .webm)")
        print("  输出频率: 每秒输出次数，默认为10 (可选)")
        print("  --save-video: 导出骨架叠加视频 *_skeleton.mp4 (可选)")
        print("示例:")
        print("  python pose_estimator_video.py video.mp4")
        print("  python pose_estimator_video.py video.mp4 10")
        print("  python pose_estimator_video.py video.mp4 10 --save-video")
        return
    
    video_path = sys.argv[1]
    extra_args = sys.argv[2:]
    save_video = '--save-video' in extra_args
    target_fps = 10
    for arg in extra_args:
        if arg.startswith('--'):
            continue
        target_fps = int(arg)
        break
    
    if not os.path.exists(video_path):
        print(f"错误: 视频文件不存在 {video_path}")
        return
    
    # 检查文件格式
    file_ext = os.path.splitext(video_path)[1].lower()
    supported_formats = ['.mp4', '.avi', '.mov', '.mkv', '.wmv', '.flv', '.webm']
    
    if file_ext not in supported_formats:
        print(f"错误: 不支持的视频格式 {file_ext}")
        print(f"支持的格式: {', '.join(supported_formats)}")
        return
    
    print(f"开始处理视频: {video_path}")
    print(f"输出频率: 每秒{target_fps}次")
    if save_video:
        print("骨架视频导出: 开启")
    print("=" * 60)
    
    # 创建视频姿态估计器
    estimator = VideoPoseEstimator()
    
    # 定义结果回调函数（可选，用于实时处理）
    def result_callback(frame_num, timestamp, result):
        if result['success']:
            # 这里可以添加实时处理逻辑
            # 例如：发送到机器人、保存到数据库等
            pass
    
    # 处理视频
    results = estimator.process_video(
        video_path,
        callback=result_callback,
        target_fps=target_fps,
        save_skeleton_video=save_video,
    )
    
    if results:
        successful_results = [r for r in results if r['success']]
        
        if successful_results:
            print("\n" + "="*60)
            print("处理结果汇总:")
            
            # 显示最后一次成功检测的角度信息
            last_result = successful_results[-1]
            print(f"\n最后一次成功检测 (时间: {last_result['video_timestamp']:.2f}s):")
            print("关节角度排列: [LShoulderPitch, LShoulderRoll, LElbowYaw, LElbowRoll, RShoulderPitch, RShoulderRoll, RElbowYaw, RElbowRoll, HipPitch]")
            print(f"弧度: {[f'{x:.4f}' for x in last_result['angles']['angles_rad']]}")
            print(f"角度: {[f'{x:.2f}' for x in last_result['angles']['angles_deg']]}")
            
            # 询问是否保存结果
            try:
                save_choice = input("\n是否保存所有结果到JSON文件? (y/n): ").lower().strip()
                if save_choice == 'y':
                    output_file = os.path.splitext(video_path)[0] + "_pose_results.json"
                    estimator.save_results_to_json(results, output_file)
            except KeyboardInterrupt:
                print("\n用户取消操作")
        else:
            print("错误: 整个视频中未成功检测到任何人体姿态")
    else:
        print("错误: 视频处理失败")


if __name__ == '__main__':
    main()