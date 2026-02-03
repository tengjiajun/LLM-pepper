#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
姿态分析服务器
接收客户端图片，调用pose_estimator.py进行姿态分析，返回Pepper机器人关节角度数据
"""

import os
import json
import time
import uuid
import sys
import math
import logging
from datetime import datetime
from pathlib import Path
from flask import Flask, request, jsonify, Response, stream_with_context
import cv2
import mediapipe as mp
from PIL import Image
import io
from pose_estimator import PoseEstimator
from utils.drawlandmarks import (
    calc_bounding_rect as utils_calc_bounding_rect,
    draw_landmarks as utils_draw_landmarks,
    draw_bounding_rect as utils_draw_bounding_rect,
)
from utils.cvfpscalc import CvFpsCalc
from utils.butterworth_lowpass import ButterworthLowpassBank

# 配置日志
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('pose_analysis_server.log', encoding='utf-8'),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)

app = Flask(__name__)

mp_drawing = mp.solutions.drawing_utils
mp_drawing_styles = mp.solutions.drawing_styles
WINDOW_NAME = "External Video Pose"
ANGLE_STABILITY_THRESHOLD = 0.2618  # ≈15°，用于帧间稳定处理

if hasattr(mp_drawing_styles, "get_default_pose_landmarks_style"):
    DEFAULT_POSE_LANDMARK_STYLE = mp_drawing_styles.get_default_pose_landmarks_style()
else:
    logger.warning(
        "MediaPipe drawing_styles缺少get_default_pose_landmarks_style，使用降级绘制样式"
    )
    DEFAULT_POSE_LANDMARK_STYLE = mp_drawing.DrawingSpec(color=(0, 255, 0), thickness=2, circle_radius=2)

if hasattr(mp_drawing_styles, "get_default_pose_connections_style"):
    DEFAULT_POSE_CONNECTION_STYLE = mp_drawing_styles.get_default_pose_connections_style()
else:
    logger.warning(
        "MediaPipe drawing_styles缺少get_default_pose_connections_style，使用降级绘制样式"
    )
    DEFAULT_POSE_CONNECTION_STYLE = mp_drawing.DrawingSpec(color=(255, 0, 0), thickness=2, circle_radius=2)

# 添加CORS支持，允许网页客户端访问
@app.after_request
def after_request(response):
    response.headers.add('Access-Control-Allow-Origin', '*')
    response.headers.add('Access-Control-Allow-Headers', 'Content-Type,Authorization')
    response.headers.add('Access-Control-Allow-Methods', 'GET,PUT,POST,DELETE,OPTIONS')
    return response

class PoseAnalysisServer:
    def __init__(self):
        # 创建assets目录
        self.assets_dir = Path("assets")
        self.assets_dir.mkdir(exist_ok=True)
        
        # 支持的图片格式
        self.supported_formats = {'.jpg', '.jpeg', '.png', '.bmp'}
        
        # 初始化姿态估计器
        self.pose_estimator = PoseEstimator()
        
        logger.info("PoseAnalysisServer 初始化完成")
        logger.info(f"Assets目录: {self.assets_dir.absolute()}")
    
    def generate_unique_filename(self, original_filename):
        """生成唯一的文件名"""
        # 获取文件扩展名
        file_ext = Path(original_filename).suffix.lower()
        
        # 生成UUID + 时间戳
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        unique_id = str(uuid.uuid4())[:8]
        
        # 组合成唯一文件名
        unique_filename = f"{timestamp}_{unique_id}{file_ext}"
        return unique_filename
    
    def save_uploaded_image(self, file):
        """保存上传的图片到assets目录"""
        try:
            # 验证文件
            if not file or not file.filename:
                raise ValueError("无效的文件")
            
            # 检查文件格式
            file_ext = Path(file.filename).suffix.lower()
            if file_ext not in self.supported_formats:
                raise ValueError(f"不支持的文件格式: {file_ext}")
            
            # 读取图片数据并验证
            img_bytes = file.read()
            if len(img_bytes) == 0:
                raise ValueError("文件为空")
            
            # 验证是否为有效图片
            try:
                img = Image.open(io.BytesIO(img_bytes))
                img.verify()  # 验证图片完整性
                logger.info(f"图片验证成功: 格式={img.format}, 尺寸={img.size}, 大小={len(img_bytes)}字节")
            except Exception as e:
                raise ValueError(f"无效的图片文件: {e}")
            
            # 生成唯一文件名并保存
            unique_filename = self.generate_unique_filename(file.filename)
            save_path = self.assets_dir / unique_filename
            
            # 重新读取文件内容并保存（因为verify()会消耗文件指针）
            file.seek(0)
            img_bytes = file.read()
            
            with open(save_path, 'wb') as f:
                f.write(img_bytes)
            
            logger.info(f"图片保存成功: {save_path}")
            return str(save_path)
            
        except Exception as e:
            logger.error(f"保存图片失败: {e}")
            raise
    
    def analyze_pose_and_extract_angles(self, image_path):
        """分析姿态并提取关节角度"""
        try:
            logger.info(f"开始姿态分析: {image_path}")
            
            # 使用pose_estimator进行姿态估计
            result = self.pose_estimator.estimate_pose(image_path)
            
            if result is None or not result['success']:
                raise RuntimeError("姿态估计失败：未检测到人体姿态或图片无效")
            
            # 检查安全限制
            if not result['safety_check']['all_safe']:
                logger.warning("部分关节角度超出安全范围")
                # 这里可以选择是否要应用限制
                # 目前我们仍然返回结果，但会在响应中标记
            
            # 提取弧度制的角度
            angles_rad = result['angles']['angle_dict_rad']
            
            # 转换为角度制，并按您要求的格式返回
            angles_deg = {
                'LShoulderPitch': math.degrees(angles_rad['LShoulderPitch']),
                'RShoulderPitch': math.degrees(angles_rad['RShoulderPitch']),
                'LShoulderRoll': math.degrees(angles_rad['LShoulderRoll']),
                'RShoulderRoll': math.degrees(angles_rad['RShoulderRoll']),
                'LElbowYaw': math.degrees(angles_rad['LElbowYaw']),
                'RElbowYaw': math.degrees(angles_rad['RElbowYaw']),
                'LElbowRoll': math.degrees(angles_rad['LElbowRoll']),
                'RElbowRoll': math.degrees(angles_rad['RElbowRoll'])
            }
            
            logger.info("姿态分析完成，成功提取关节角度")
            
            return {
                'angles_deg': angles_deg,
                'angles_rad': angles_rad,
                'safety_check': result['safety_check']
            }
            
        except Exception as e:
            logger.error(f"姿态分析失败: {e}")
            raise

# 创建服务器实例
pose_server = PoseAnalysisServer()

@app.route('/health', methods=['GET'])
def health_check():
    """健康检查接口"""
    return jsonify({
        "status": "healthy",
        "service": "MediaPipe Pose Analysis Server",
        "timestamp": datetime.now().isoformat()
    })

@app.route('/analyze_pose', methods=['POST'])
def analyze_pose():
    """姿态分析接口"""
    request_id = str(uuid.uuid4())[:8]
    start_time = time.time()
    
    logger.info(f"[{request_id}] 收到姿态分析请求")
    
    try:
        # 检查是否有图片上传
        if 'image' not in request.files:
            logger.warning(f"[{request_id}] 请求中没有图片文件")
            return jsonify({
                'error': 'No image uploaded',
                'message': '请在请求中包含名为"image"的图片文件'
            }), 400
        
        file = request.files['image']
        if not file.filename:
            logger.warning(f"[{request_id}] 空文件名")
            return jsonify({
                'error': 'Empty filename',
                'message': '文件名不能为空'
            }), 400
        
        logger.info(f"[{request_id}] 接收到图片: {file.filename}")
        
        # 保存图片
        try:
            image_path = pose_server.save_uploaded_image(file)
            logger.info(f"[{request_id}] 图片保存成功: {image_path}")
        except Exception as e:
            logger.error(f"[{request_id}] 保存图片失败: {e}")
            return jsonify({
                'error': 'Failed to save image',
                'message': str(e)
            }), 400
        
        # 运行姿态分析
        try:
            result = pose_server.analyze_pose_and_extract_angles(image_path)
            logger.info(f"[{request_id}] 姿态分析完成")
        except Exception as e:
            logger.error(f"[{request_id}] 姿态分析失败: {e}")
            return jsonify({
                'error': 'Pose analysis failed',
                'message': str(e)
            }), 500
        
        # 计算处理时间
        processing_time = time.time() - start_time
        
        # 准备响应数据 - 返回弧度制角度
        joint_names = ["LShoulderPitch", "RShoulderPitch", "LShoulderRoll", "RShoulderRoll", 
                       "LElbowYaw", "RElbowYaw", "LElbowRoll", "RElbowRoll"]
        
        # 按照joint_names的顺序提取弧度制角度值
        angle_values = [
            result['angles_rad']['LShoulderPitch'],
            result['angles_rad']['RShoulderPitch'],
            result['angles_rad']['LShoulderRoll'],
            result['angles_rad']['RShoulderRoll'],
            result['angles_rad']['LElbowYaw'],
            result['angles_rad']['RElbowYaw'],
            result['angles_rad']['LElbowRoll'],
            result['angles_rad']['RElbowRoll']
        ]
        
        response_data = {
            'joint_names': joint_names,
            'angles': angle_values,
            'function': 'analyze_pose',
            # 附加信息
            'success': True
        }
        
        logger.info(f"[{request_id}] 请求处理成功，耗时: {processing_time:.2f}秒")
        return jsonify(response_data)
        
    except Exception as e:
        logger.error(f"[{request_id}] 请求处理异常: {e}")
        return jsonify({
            'error': 'Internal server error',
            'message': str(e),
            'request_id': request_id
        }), 500

@app.route('/analyze_pose_batch', methods=['POST'])
def analyze_pose_batch():
    """批量姿态分析接口 - 处理多张图片"""
    request_id = str(uuid.uuid4())[:8]
    start_time = time.time()
    
    logger.info(f"[{request_id}] 收到批量姿态分析请求")
    
    try:
        # 检查是否有图片上传
        if 'images' not in request.files:
            logger.warning(f"[{request_id}] 请求中没有图片文件")
            return jsonify({
                'error': 'No images uploaded',
                'message': '请在请求中包含名为"images"的图片文件（支持多文件上传）'
            }), 400
        
        uploaded_files = request.files.getlist('images')
        if not uploaded_files or len(uploaded_files) == 0:
            logger.warning(f"[{request_id}] 未上传任何图片")
            return jsonify({
                'error': 'No images provided',
                'message': '请至少上传一张图片'
            }), 400
        
        logger.info(f"[{request_id}] 接收到 {len(uploaded_files)} 张图片")
        
        # 批量保存图片
        saved_image_paths = []
        saved_image_names = []
        for idx, file in enumerate(uploaded_files):
            if not file.filename:
                logger.warning(f"[{request_id}] 第{idx+1}张图片文件名为空，跳过")
                continue
            
            try:
                image_path = pose_server.save_uploaded_image(file)
                saved_image_paths.append(image_path)
                saved_image_names.append(os.path.basename(image_path))
                logger.info(f"[{request_id}] 第{idx+1}张图片保存成功: {os.path.basename(image_path)}")
            except Exception as e:
                logger.error(f"[{request_id}] 第{idx+1}张图片保存失败: {e}")
                # 继续处理其他图片，不因为一张图片失败而终止
                continue
        
        if not saved_image_paths:
            logger.error(f"[{request_id}] 没有成功保存任何图片")
            return jsonify({
                'error': 'Failed to save any images',
                'message': '所有图片保存失败，请检查图片格式和内容'
            }), 400
        
        logger.info(f"[{request_id}] 成功保存 {len(saved_image_paths)} 张图片，开始批量分析")
        
        # 批量姿态分析
        joint_names = [
            "LShoulderPitch", "RShoulderPitch", "LShoulderRoll", "RShoulderRoll",
            "LElbowYaw", "RElbowYaw", "LElbowRoll", "RElbowRoll"
        ]

        # 初始化结果字典与上一帧记录
        result_data = {joint_name: [] for joint_name in joint_names}
        prev_valid_angles = {joint_name: None for joint_name in joint_names}
        successful_analyses = 0
        failed_analyses = 0
        all_safety_checks = []
        
        # 逐一分析每张图片
        for idx, image_path in enumerate(saved_image_paths):
            try:
                logger.info(f"[{request_id}] 分析第{idx+1}张图片: {os.path.basename(image_path)}")
                analysis_result = pose_server.analyze_pose_and_extract_angles(image_path)

                # 提取每个关节的角度值（弧度制），并与上一帧比较
                for joint_name in joint_names:
                    angle_value = analysis_result['angles_rad'][joint_name]
                    prev_value = prev_valid_angles[joint_name]

                    if (
                        angle_value is not None
                        and prev_value is not None
                        and abs(angle_value - prev_value) < ANGLE_STABILITY_THRESHOLD
                    ):
                        adjusted_angle = prev_value
                    else:
                        adjusted_angle = angle_value

                    result_data[joint_name].append(adjusted_angle)

                    if adjusted_angle is not None:
                        prev_valid_angles[joint_name] = adjusted_angle

                all_safety_checks.append(analysis_result['safety_check']['all_safe'])
                successful_analyses += 1

                logger.info(f"[{request_id}] 第{idx+1}张图片分析完成")

            except Exception as e:
                logger.error(f"[{request_id}] 第{idx+1}张图片分析失败: {e}")
                failed_analyses += 1

                # 为失败的图片添加 null 值，保持数组长度一致
                for joint_name in joint_names:
                    result_data[joint_name].append(None)
                all_safety_checks.append(False)
                # 继续处理下一张图片
                continue

        # 计算处理时间
        processing_time = time.time() - start_time

        # 检查是否有成功的分析结果
        if successful_analyses == 0:
            logger.error(f"[{request_id}] 所有图片分析失败")
            return jsonify({
                'error': 'All pose analyses failed',
                'message': '所有图片的姿态分析都失败了',
                'request_id': request_id
            }), 500

        response_data = {
            'success': True,
            'function': 'analyze_pose_batch',
            'request_id': request_id,
            'total_images': len(saved_image_paths),
            'processing_time_sec': processing_time,
            'saved_images': saved_image_names,
            'successful_analyses': successful_analyses,
            'failed_analyses': failed_analyses,
            'safety_check': all(all_safety_checks),
            'safety_checks': all_safety_checks,
            'timestamp': datetime.now().isoformat()
        }

        # 添加每个关节的角度数组
        for joint_name in joint_names:
            response_data[joint_name] = result_data[joint_name]
        
        logger.info(f"[{request_id}] 批量分析完成，成功: {successful_analyses}, 失败: {failed_analyses}, 耗时: {processing_time:.2f}秒")
        return jsonify(response_data)
        
    except Exception as e:
        logger.error(f"[{request_id}] 批量请求处理异常: {e}")
        return jsonify({
            'error': 'Internal server error',
            'message': str(e),
            'request_id': request_id
        }), 500

@app.route('/open_external_video', methods=['POST'])
def open_external_video():
    """打开本地摄像头并实时返回姿态分析结果（流式响应）"""
    request_id = str(uuid.uuid4())[:8]
    params = request.get_json(silent=True) or {}
    camera_index = int(params.get('camera_index', 0))
    capture_fps = float(params.get('capture_fps', 30.0))
    output_fps = float(params.get('output_fps', 10.0))
    frame_width = int(params.get('width', 1280))
    frame_height = int(params.get('height', 720))
    show_window = bool(params.get('show_window', True))
    use_brect = bool(params.get('use_brect', False))

    logger.info(
        f"[{request_id}] 收到实时视频姿态请求: camera_index={camera_index}, capture_fps={capture_fps}, output_fps={output_fps}, show_window={show_window}"
    )

    cap = cv2.VideoCapture(camera_index)
    if not cap.isOpened():
        logger.error(f"[{request_id}] 无法打开摄像头 {camera_index}")
        return jsonify({
            'error': 'Failed to open camera',
            'message': f'Failed to open camera {camera_index}',
            'function': 'open_external_video',
            'request_id': request_id
        }), 500

    cap.set(cv2.CAP_PROP_FRAME_WIDTH, frame_width)
    cap.set(cv2.CAP_PROP_FRAME_HEIGHT, frame_height)
    cap.set(cv2.CAP_PROP_FPS, capture_fps)

    joint_names = [
        "LShoulderPitch", "RShoulderPitch",
        "LShoulderRoll", "RShoulderRoll",
        "LElbowYaw", "RElbowYaw",
        "LElbowRoll", "RElbowRoll",
        "HeadPitch", "HipPitch"
    ]

    frame_interval = 1.0 / max(output_fps, 1.0)

    # 配置 Butterworth 低通滤波器
    sampling_rate = max(output_fps, 1.0)
    cutoff_hz = float(params.get('cutoff_hz', 10.0))
    cutoff_hz = max(0.1, cutoff_hz)
    nyquist = 0.5 * sampling_rate
    if cutoff_hz >= nyquist and nyquist > 0:
        cutoff_hz = max(0.1, nyquist * 0.95)

    filter_order = int(params.get('filter_order', 1))
    if filter_order < 1:
        filter_order = 1

    try:
        filter_bank = ButterworthLowpassBank(
            cutoff_hz=cutoff_hz,
            fs=sampling_rate,
            order=filter_order,
            channel_names=joint_names
        )
        filters_initialized = False
    except ValueError as e:
        logger.error(f"[{request_id}] 初始化Butterworth滤波器失败，将使用未滤波数据: {e}")
        filter_bank = None
        filters_initialized = False
    fps_calc = CvFpsCalc(buffer_len=10) if show_window else None
    stability_prev_angles = {joint: None for joint in joint_names}

    def stream_frames():
        nonlocal filter_bank, filters_initialized, stability_prev_angles
        last_sent_time = 0.0
        window_created = False
        stop_stream = False
        try:
            while True:
                ret, frame = cap.read()
                if not ret:
                    logger.warning(f"[{request_id}] 摄像头读取失败，结束流")
                    payload = {
                        'success': False,
                        'function': 'open_external_video',
                        'joint_names': joint_names,
                        'angles': [None] * len(joint_names),
                        'angles_deg': [None] * len(joint_names),
                        'error': 'Failed to read frame from camera'
                    }
                    yield json.dumps(payload, ensure_ascii=True) + '\n'
                    break

                display_frame = frame.copy() if show_window else None

                if show_window and not window_created and display_frame is not None:
                    cv2.namedWindow(WINDOW_NAME, cv2.WINDOW_NORMAL)
                    window_created = True

                fps_value = fps_calc.get() if fps_calc else None
                current_time = time.time()
                should_send = (current_time - last_sent_time) >= frame_interval

                try:
                    success, results = pose_server.pose_estimator.process_image(frame)
                except Exception as e:
                    logger.error(f"[{request_id}] 姿态估计异常: {e}")
                    success, results = False, None

                clamp_events = []
                if success and results:
                    angle_result = pose_server.pose_estimator.calculate_angles(results.pose_world_landmarks)
                    angle_dict_rad = angle_result['angle_dict_rad']

                    clamped_angles_rad = []
                    stabilized_angles_rad = []

                    for joint_name in joint_names:
                        raw_angle = angle_dict_rad.get(joint_name)
                        limits = pose_server.pose_estimator.joint_limits.get(joint_name)
                        clamped_angle = raw_angle
                        if limits is not None and raw_angle is not None:
                            clamped_angle = max(limits[0], min(raw_angle, limits[1]))
                            if not math.isclose(clamped_angle, raw_angle, rel_tol=1e-6, abs_tol=1e-6):
                                clamp_events.append((joint_name, raw_angle, clamped_angle, limits))

                        clamped_angles_rad.append(clamped_angle)

                        prev_value = stability_prev_angles[joint_name]
                        if (
                            clamped_angle is not None
                            and prev_value is not None
                            and abs(clamped_angle - prev_value) < ANGLE_STABILITY_THRESHOLD
                        ):
                            stabilized_angle = prev_value
                        else:
                            stabilized_angle = clamped_angle

                        stabilized_angles_rad.append(stabilized_angle)
                        if stabilized_angle is not None:
                            stability_prev_angles[joint_name] = stabilized_angle

                    if clamp_events:
                        for joint_name, raw_angle, clamped_angle, limits in clamp_events:
                            logger.warning(
                                f"[{request_id}] 关节{joint_name}超出限制({limits[0]:.4f}, {limits[1]:.4f})，已从{raw_angle:.4f}裁剪至{clamped_angle:.4f}"
                            )

                    # 对弧度值进行实时低通滤波
                    if filter_bank is None:
                        filtered_angles_rad = stabilized_angles_rad
                        filtered_angles_deg = [
                            math.degrees(angle) if angle is not None else None
                            for angle in stabilized_angles_rad
                        ]
                    else:
                        valid_inputs = {
                            joint: angle
                            for joint, angle in zip(joint_names, stabilized_angles_rad)
                            if angle is not None
                        }

                        if not valid_inputs:
                            if filter_bank is not None:
                                filter_bank.reset()
                            for joint in stability_prev_angles:
                                stability_prev_angles[joint] = None
                            filters_initialized = False
                            filtered_angles_rad = [None] * len(joint_names)
                            filtered_angles_deg = [None] * len(joint_names)
                        else:
                            if not filters_initialized:
                                try:
                                    filter_bank.reset(initial_values=valid_inputs)
                                except Exception as reset_error:
                                    logger.error(
                                        f"[{request_id}] 重置Butterworth滤波器失败，改用未滤波数据: {reset_error}"
                                    )
                                    filter_bank = None
                                    filters_initialized = False
                                    filtered_angles_rad = stabilized_angles_rad
                                    filtered_angles_deg = [
                                        math.degrees(angle) if angle is not None else None
                                        for angle in stabilized_angles_rad
                                    ]
                                else:
                                    filters_initialized = True

                            if filter_bank is not None and filters_initialized:
                                try:
                                    filtered_map = filter_bank.filter_sample(valid_inputs)
                                except Exception as filter_error:
                                    logger.error(
                                        f"[{request_id}] Butterworth滤波失败，改用未滤波数据: {filter_error}"
                                    )
                                    filter_bank = None
                                    filters_initialized = False
                                    filtered_angles_rad = stabilized_angles_rad
                                    filtered_angles_deg = [
                                        math.degrees(angle) if angle is not None else None
                                        for angle in stabilized_angles_rad
                                    ]
                                else:
                                    filtered_angles_rad = []
                                    filtered_angles_deg = []
                                    for joint in joint_names:
                                        if joint in filtered_map:
                                            value = filtered_map[joint]
                                            filtered_angles_rad.append(value)
                                            filtered_angles_deg.append(math.degrees(value))
                                        else:
                                            filtered_angles_rad.append(None)
                                            filtered_angles_deg.append(None)

                    payload = {
                        'success': True,
                        'function': 'open_external_video',
                        'joint_names': joint_names,
                        'angles': filtered_angles_rad,
                        'angles_deg': filtered_angles_deg
                    }
                else:
                    payload = {
                        'success': False,
                        'function': 'open_external_video',
                        'joint_names': joint_names,
                        'angles': [None] * len(joint_names),
                        'angles_deg': [None] * len(joint_names),
                        'error': 'No human pose detected'
                    }
                    if filter_bank is not None:
                        filter_bank.reset()
                    filters_initialized = False
                    stability_prev_angles = {joint: None for joint in joint_names}

                if show_window and display_frame is not None:
                    if success and results and results.pose_landmarks:
                        display_frame = utils_draw_landmarks(display_frame, results.pose_landmarks)
                        if use_brect:
                            brect = utils_calc_bounding_rect(display_frame, results.pose_landmarks)
                            display_frame = utils_draw_bounding_rect(True, display_frame, brect)
                    status_text = "TRACKING" if success and results else "SEARCHING"
                    status_color = (0, 0, 255) if status_text == "TRACKING" else (0, 165, 255)
                    cv2.putText(display_frame, status_text, (10, 90),
                                cv2.FONT_HERSHEY_SIMPLEX, 1.0, status_color, 2, cv2.LINE_AA)
                    if clamp_events:
                        cv2.putText(display_frame, "LIMIT", (10, 140),
                                    cv2.FONT_HERSHEY_SIMPLEX, 1.0, (0, 0, 255), 2, cv2.LINE_AA)
                    if fps_value is not None:
                        cv2.putText(display_frame, f"FPS:{fps_value}", (10, 30),
                                    cv2.FONT_HERSHEY_SIMPLEX, 1.0, (0, 145, 255), 2, cv2.LINE_AA)
                    cv2.imshow(WINDOW_NAME, display_frame)
                    if cv2.waitKey(1) & 0xFF == ord('q'):
                        logger.info(f"[{request_id}] 检测到按键退出，停止实时视频流")
                        stop_stream = True

                if stop_stream:
                    break

                if not should_send:
                    continue

                last_sent_time = current_time
                yield json.dumps(payload, ensure_ascii=True) + '\n'

                if stop_stream:
                    break

        except GeneratorExit:
            logger.info(f"[{request_id}] 客户端断开，停止实时视频流")
        except Exception as e:
            logger.error(f"[{request_id}] 实时视频流异常: {e}")
            payload = {
                'success': False,
                'function': 'open_external_video',
                'joint_names': joint_names,
                'angles': [None] * len(joint_names),
                'angles_deg': [None] * len(joint_names),
                'error': str(e)
            }
            yield json.dumps(payload, ensure_ascii=True) + '\n'
        finally:
            cap.release()
            if show_window and window_created:
                cv2.destroyWindow(WINDOW_NAME)
            logger.info(f"[{request_id}] 摄像头已关闭")

    response = Response(stream_with_context(stream_frames()), mimetype='application/json')
    response.headers['Cache-Control'] = 'no-store'
    response.headers['X-Accel-Buffering'] = 'no'
    return response

@app.route('/list_images', methods=['GET'])
def list_images():
    """列出已保存的图片"""
    try:  
        images = []
        for file_path in pose_server.assets_dir.glob('*'):
            if file_path.is_file() and file_path.suffix.lower() in pose_server.supported_formats:
                images.append({
                    'filename': file_path.name,
                    'size': file_path.stat().st_size,
                    'created_time': datetime.fromtimestamp(file_path.stat().st_ctime).isoformat()
                })
        
        return jsonify({
            'images': sorted(images, key=lambda x: x['created_time'], reverse=True),
            'total_count': len(images)
        })
    except Exception as e:
        logger.error(f"列出图片失败: {e}")
        return jsonify({'error': str(e)}), 500

@app.errorhandler(413)
def too_large(e):
    """文件太大错误处理"""
    return jsonify({
        'error': 'File too large',
        'message': '上传的文件太大，请使用较小的图片'
    }), 413

@app.errorhandler(404)
def not_found(e):
    """404错误处理"""
    return jsonify({
        'error': 'Not found',
        'message': '请求的接口不存在'
    }), 404

def main():
    """主函数"""
    print("="*60)
    print("🤖 MediaPipe姿态分析服务器")
    print("="*60)
    print(f"📁 图片保存目录: {pose_server.assets_dir.absolute()}")
    print("")
    print("📡 API接口:")
    print("  POST /analyze_pose           - 单张图片姿态分析")
    print("  POST /analyze_pose_batch - 多张图片批量姿态分析") 
    print("  GET  /health                 - 健康检查")
    print("  GET  /list_images            - 列出已保存图片")
    print("")
    print("📝 使用示例:")
    print("  # 单张图片分析")
    print("  curl -X POST -F 'image=@your_image.jpg' http://localhost:5000/analyze_pose")
    print("")
    print("  # 多张图片批量分析") 
    print("  curl -X POST -F 'images=@image1.jpg' -F 'images=@image2.jpg' -F 'images=@image3.jpg' http://localhost:5000/analyze_pose_batch")
    print("")
    print("📊 返回格式:")
    print("  单张图片: {joint_names: [...], angles: [...], ...}")
    print("  多张图片: {joint_names: [...], LShoulderPitch: [...], RShoulderPitch: [...], ...}")
    print("")
    print("🔍 日志文件: pose_analysis_server.log")
    print("="*60)
    
    try:
        # 启动服务器
        app.run(
            host='0.0.0.0',
            port=5000,
            debug=False,
            threaded=True
        )
    except KeyboardInterrupt:
        print("\n👋 服务器已停止")
    except Exception as e:
        print(f"❌ 服务器启动失败: {e}")

if __name__ == '__main__':
    main()
