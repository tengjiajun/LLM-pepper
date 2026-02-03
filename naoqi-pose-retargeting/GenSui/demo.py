#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""
基于VLM的机器人跟随系统
使用笔记本前置摄像头和Vision-Language Model实现机器人跟随功能
当前版本输出控制信号到控制台，可适配到Pepper机器人

作者: GitHub Copilot
环境: conda activate naoqi-pose
依赖: opencv-python, requests, base64, json
"""

import cv2
import numpy as np
import requests
import base64
import json
import time
import logging
import os
from datetime import datetime
from typing import Dict, List, Optional, Tuple, Any
import threading
from queue import Queue


class Config:
    """配置管理类"""
    
    # 摄像头配置
    CAMERA_INDEX = 0
    CAMERA_WIDTH = 640
    CAMERA_HEIGHT = 480
    CAMERA_FPS = 10
    
    # VLM配置 - OpenAI GPT-4 Vision API
    OPENAI_API_KEY = os.getenv("OPENAI_API_KEY", "your-api-key-here")
    OPENAI_API_URL = "https://api.openai.com/v1/chat/completions"
    OPENAI_MODEL = "gpt-4-vision-preview"
    
    # 替代方案 - Hugging Face API (如LLaVA)
    HF_API_TOKEN = os.getenv("HF_API_TOKEN", "your-hf-token-here")
    HF_API_URL = "https://api-inference.huggingface.co/models/llava-hf/llava-1.5-7b-hf"
    
    # 本地开源模型 - Qwen2-VL (Owen)
    USE_QWEN = False  # 置为 True 启用本地Qwen视觉模型
    QWEN_MODEL_NAME = os.getenv("QWEN_MODEL_NAME", "Qwen/Qwen2-VL-2B-Instruct")  # 体积小便于测试
    QWEN_DEVICE = os.getenv("QWEN_DEVICE", "cpu")  # 可改为 'cuda' or 'cuda:0'
    QWEN_DTYPE = os.getenv("QWEN_DTYPE", "auto")  # 'auto' / 'float16' / 'bfloat16'
    QWEN_MAX_TOKENS = 400

    # Qwen 云端 API（阿里灵积/通义千问多模态）
    USE_QWEN_API = False  # True 时调用云端 Qwen VLM，而非本地模型
    QWEN_API_KEY = os.getenv("QWEN_API_KEY", "sk-32e369888c6a48f1918d0f2e0b3488a1")
    QWEN_API_URL = os.getenv("QWEN_API_URL", "https://dashscope.aliyuncs.com/api/v1/services/aigc/multimodal-generation/generation")  # 视官方文档可能更新
    QWEN_API_MODEL = os.getenv("QWEN_API_MODEL", "qwen-vl-plus")  # 示例：qwen-vl-plus / qwen-vl-max / qwen-vl-chat

    # 系统配置
    USE_OPENAI = True  # True使用OpenAI，False使用Hugging Face (若USE_QWEN/USE_QWEN_API=True则优先对应)
    FRAME_INTERVAL = 0.1  # 处理帧间隔（秒）
    LOG_LEVEL = logging.INFO
    
    # 机器人控制参数
    MAX_SPEED = 0.5  # 最大移动速度 (m/s)
    MAX_TURN_SPEED = 0.3  # 最大转向速度 (rad/s)
    SAFE_DISTANCE = 1.5  # 安全跟随距离 (m)
    
    # Pepper机器人连接配置（适配时使用）
    PEPPER_IP = "192.168.1.100"  # Pepper机器人IP地址
    PEPPER_PORT = 9559  # NAOqi端口


class Logger:
    """日志管理类"""
    
    def __init__(self, name="robot_following", level=Config.LOG_LEVEL):
        self.logger = logging.getLogger(name)
        self.logger.setLevel(level)
        
        # 创建控制台处理器
        console_handler = logging.StreamHandler()
        console_handler.setLevel(level)
        
        # 创建文件处理器
        log_filename = f"robot_following_{datetime.now().strftime('%Y%m%d_%H%M%S')}.log"
        file_handler = logging.FileHandler(log_filename, encoding='utf-8')
        file_handler.setLevel(level)
        
        # 设置格式
        formatter = logging.Formatter(
            '%(asctime)s - %(name)s - %(levelname)s - %(message)s'
        )
        console_handler.setFormatter(formatter)
        file_handler.setFormatter(formatter)
        
        # 添加处理器
        if not self.logger.handlers:
            self.logger.addHandler(console_handler)
            self.logger.addHandler(file_handler)
    
    def info(self, message):
        self.logger.info(message)
    
    def warning(self, message):
        self.logger.warning(message)
    
    def error(self, message):
        self.logger.error(message)
    
    def debug(self, message):
        self.logger.debug(message)


class VLMPerception:
    """VLM感知模块"""
    
    def __init__(self, logger: Logger):
        self.logger = logger
        self.camera = None
        self.is_camera_open = False
        # Qwen 模型占位
        self._qwen_model = None
        self._qwen_processor = None
        self._qwen_available = False
        
        # 初始化摄像头
        self._init_camera()
        
        # VLM提示模板
        self.perception_prompt = """
        分析这张图片进行机器人导航：
        1. 检测图像中的人（目标跟随对象）
        2. 估计人的位置（左侧/中心/右侧）和距离（米，基于透视和大小估算）
        3. 识别可能影响跟随的障碍物
        4. 返回JSON格式：
        {
            "target": {
                "detected": true/false,
                "position": "left/center/right",
                "distance": 估计距离(米),
                "confidence": 0.0-1.0
            },
            "obstacles": ["障碍物描述列表"],
            "scene_description": "简要场景描述",
            "navigation_advice": "导航建议"
        }
        
        注意：基于人体在图像中的大小和位置估计距离，成年人身高约1.7米作为参考。
        """
    
    def _init_camera(self):
        """初始化摄像头"""
        try:
            self.camera = cv2.VideoCapture(Config.CAMERA_INDEX)
            if self.camera.isOpened():
                self.camera.set(cv2.CAP_PROP_FRAME_WIDTH, Config.CAMERA_WIDTH)
                self.camera.set(cv2.CAP_PROP_FRAME_HEIGHT, Config.CAMERA_HEIGHT)
                self.camera.set(cv2.CAP_PROP_FPS, Config.CAMERA_FPS)
                self.is_camera_open = True
                self.logger.info(f"摄像头初始化成功: {Config.CAMERA_WIDTH}x{Config.CAMERA_HEIGHT}")
            else:
                self.logger.error("无法打开摄像头")
        except Exception as e:
            self.logger.error(f"摄像头初始化失败: {e}")
    
    def capture_frame(self) -> Optional[np.ndarray]:
        """捕获一帧图像"""
        if not self.is_camera_open:
            return None
        
        ret, frame = self.camera.read()
        if ret:
            return frame
        else:
            self.logger.warning("图像捕获失败")
            return None
    
    def _encode_image_to_base64(self, image: np.ndarray) -> str:
        """将图像编码为base64字符串"""
        _, buffer = cv2.imencode('.jpg', image)
        image_base64 = base64.b64encode(buffer).decode('utf-8')
        return image_base64
    
    def _call_openai_vision(self, image_base64: str) -> Optional[Dict]:
        """调用OpenAI GPT-4 Vision API"""
        headers = {
            "Content-Type": "application/json",
            "Authorization": f"Bearer {Config.OPENAI_API_KEY}"
        }
        
        payload = {
            "model": Config.OPENAI_MODEL,
            "messages": [
                {
                    "role": "user",
                    "content": [
                        {
                            "type": "text",
                            "text": self.perception_prompt
                        },
                        {
                            "type": "image_url",
                            "image_url": {
                                "url": f"data:image/jpeg;base64,{image_base64}"
                            }
                        }
                    ]
                }
            ],
            "max_tokens": 500
        }
        
        try:
            response = requests.post(Config.OPENAI_API_URL, headers=headers, json=payload, timeout=10)
            if response.status_code == 200:
                result = response.json()
                content = result['choices'][0]['message']['content']
                
                # 尝试解析JSON
                try:
                    # 提取JSON部分
                    if '```json' in content:
                        json_start = content.find('```json') + 7
                        json_end = content.find('```', json_start)
                        json_str = content[json_start:json_end].strip()
                    elif '{' in content and '}' in content:
                        json_start = content.find('{')
                        json_end = content.rfind('}') + 1
                        json_str = content[json_start:json_end]
                    else:
                        json_str = content
                    
                    return json.loads(json_str)
                except json.JSONDecodeError:
                    self.logger.warning(f"无法解析VLM返回的JSON: {content}")
                    return self._parse_text_response(content)
            else:
                self.logger.error(f"OpenAI API调用失败: {response.status_code}")
                return None
        except Exception as e:
            self.logger.error(f"OpenAI API调用异常: {e}")
            return None
    
    def _call_huggingface_api(self, image_base64: str) -> Optional[Dict]:
        """调用Hugging Face API（LLaVA等）"""
        headers = {"Authorization": f"Bearer {Config.HF_API_TOKEN}"}
        
        # 简化的提示，因为HF API可能不支持复杂的JSON格式要求
        simple_prompt = "Describe the people and obstacles in this image for robot navigation."
        
        payload = {
            "inputs": {
                "image": image_base64,
                "text": simple_prompt
            }
        }
        
        try:
            response = requests.post(Config.HF_API_URL, headers=headers, json=payload, timeout=15)
            if response.status_code == 200:
                result = response.json()
                # HF API返回格式可能不同，需要适配
                if isinstance(result, list) and len(result) > 0:
                    text_result = result[0].get('generated_text', '')
                    return self._parse_text_response(text_result)
                else:
                    return self._parse_text_response(str(result))
            else:
                self.logger.error(f"Hugging Face API调用失败: {response.status_code}")
                return None
        except Exception as e:
            self.logger.error(f"Hugging Face API调用异常: {e}")
            return None
    
    def _parse_text_response(self, text: str) -> Dict:
        """解析文本响应，提取关键信息"""
        # 简单的文本解析，提取关键词
        text_lower = text.lower()
        
        # 检测人
        person_detected = any(word in text_lower for word in ['person', 'people', 'human', 'man', 'woman', '人'])
        
        # 估计位置
        position = "center"
        if any(word in text_lower for word in ['left', '左']):
            position = "left"
        elif any(word in text_lower for word in ['right', '右']):
            position = "right"
        
        # 估计距离（简单规则）
        distance = 2.0  # 默认距离
        if any(word in text_lower for word in ['close', 'near', '近']):
            distance = 1.0
        elif any(word in text_lower for word in ['far', '远']):
            distance = 3.0
        
        # 检测障碍物
        obstacles = []
        if any(word in text_lower for word in ['table', 'chair', 'obstacle', '桌子', '椅子', '障碍']):
            obstacles.append("furniture detected")
        
        return {
            "target": {
                "detected": person_detected,
                "position": position,
                "distance": distance,
                "confidence": 0.7 if person_detected else 0.1
            },
            "obstacles": obstacles,
            "scene_description": text[:100] + "..." if len(text) > 100 else text,
            "navigation_advice": "proceed with caution"
        }
    
    def _load_qwen_model(self):
        """惰性加载Qwen本地视觉语言模型"""
        if self._qwen_model or not Config.USE_QWEN:
            return
        try:
            import importlib
            if importlib.util.find_spec("transformers") is None:
                self.logger.error("未安装 transformers，无法加载Qwen。请先: pip install transformers accelerate sentencepiece safetensors")
                return
            if importlib.util.find_spec("torch") is None:
                self.logger.error("未安装 torch，无法加载Qwen。请根据平台安装CPU或GPU版本。")
                return
            from transformers import AutoModelForCausalLM, AutoTokenizer, AutoProcessor
            import torch
            model_name = Config.QWEN_MODEL_NAME
            self.logger.info(f"正在加载Qwen模型: {model_name} (可能需要几秒)...")
            kwargs = {"device_map": "auto" if Config.QWEN_DEVICE.startswith("cuda") else None}
            if Config.QWEN_DTYPE != "auto":
                kwargs["torch_dtype"] = getattr(torch, Config.QWEN_DTYPE)
            # 优先尝试带Processor（适配多模态）
            try:
                self._qwen_processor = AutoProcessor.from_pretrained(model_name, trust_remote_code=True)
            except Exception:
                try:
                    self._qwen_processor = AutoTokenizer.from_pretrained(model_name, trust_remote_code=True)
                except Exception as e:
                    self.logger.error(f"加载Qwen处理器失败: {e}")
                    return
            self._qwen_model = AutoModelForCausalLM.from_pretrained(
                model_name,
                trust_remote_code=True,
                **kwargs
            )
            self._qwen_model.eval()
            self._qwen_available = True
            self.logger.info("Qwen模型加载完成")
        except Exception as e:
            self.logger.error(f"Qwen模型加载失败: {e}")

    def _call_qwen_local(self, image: np.ndarray) -> Optional[Dict]:
        """使用本地Qwen多模态模型进行场景分析"""
        if not Config.USE_QWEN:
            return None
        # 确保模型已加载
        self._load_qwen_model()
        if not self._qwen_available:
            return None
        try:
            from PIL import Image
            import torch
            # OpenCV BGR -> RGB
            rgb = cv2.cvtColor(image, cv2.COLOR_BGR2RGB)
            pil_img = Image.fromarray(rgb)
            prompt = ("你是一个机器人跟随视觉助手。请严格输出 JSON："\
                      "{\\n  \"target\": { \"detected\": true/false, \"position\": \"left/center/right\", \"distance\": 距离(米数字), \"confidence\": 0-1 },"\
                      "\n  \"obstacles\": [""障碍物描述""],\n  \"scene_description\": \"...\",\n  \"navigation_advice\": \"...\"\n}\n不要输出额外文字。")
            processor = self._qwen_processor
            model = self._qwen_model
            # 兼容不同processor接口
            if hasattr(processor, "__call__"):
                inputs = processor(text=prompt, images=pil_img, return_tensors="pt") if 'images' in processor.__call__.__code__.co_varnames else processor(prompt, return_tensors="pt")
            else:
                self.logger.error("Qwen processor不支持调用")
                return None
            # 将tensor移动到对应设备
            device = Config.QWEN_DEVICE
            if device.startswith("cuda") and torch.cuda.is_available():
                inputs = {k: v.to(device) for k, v in inputs.items() if hasattr(v, 'to')}
                model.to(device)
            with torch.no_grad():
                generate_ids = model.generate(**inputs, max_new_tokens=Config.QWEN_MAX_TOKENS)
            if hasattr(processor, 'batch_decode'):
                output = processor.batch_decode(generate_ids, skip_special_tokens=True)[0]
            else:
                from transformers import AutoTokenizer
                tok = AutoTokenizer.from_pretrained(Config.QWEN_MODEL_NAME, trust_remote_code=True)
                output = tok.batch_decode(generate_ids, skip_special_tokens=True)[0]
            # 解析JSON
            json_str = None
            if '```json' in output:
                s = output.find('```json') + 7
                e = output.find('```', s)
                json_str = output[s:e].strip()
            elif '{' in output and '}' in output:
                json_str = output[output.find('{'):output.rfind('}')+1]
            if json_str:
                try:
                    return json.loads(json_str)
                except Exception:
                    self.logger.warning("Qwen输出JSON解析失败，回退文本解析")
            return self._parse_text_response(output)
        except Exception as e:
            self.logger.error(f"Qwen本地推理失败: {e}")
            return None

    def _call_qwen_api(self, image_base64: str) -> Optional[Dict]:
        """调用 Qwen 云端多模态 API (DashScope / 通义千问 VLM)"""
        if not Config.USE_QWEN_API or not Config.QWEN_API_KEY:
            return None
        headers = {
            "Content-Type": "application/json",
            "Authorization": f"Bearer {Config.QWEN_API_KEY}",
            # DashScope 也可能用 X-DashScope-Token，根据实际文档微调
        }
        # Qwen 多模态消息格式（参考最新官方，如有差异需调整）
        payload = {
            "model": Config.QWEN_API_MODEL,
            "input": [
                {
                    "role": "user",
                    "content": [
                        {"text": self.perception_prompt.strip()},
                        {"image": f"data:image/jpeg;base64,{image_base64}"}
                    ]
                }
            ],
            "parameters": {
                "max_tokens": 500,
                "temperature": 0.2
            }
        }
        try:
            resp = requests.post(Config.QWEN_API_URL, headers=headers, json=payload, timeout=15)
            if resp.status_code == 200:
                data = resp.json()
                # 可能响应结构示例：{"output": {"text": "..."}} 或多段
                text = None
                if isinstance(data, dict):
                    # 尝试常见字段
                    text = (data.get("output", {}) or {}).get("text") or data.get("text")
                    if not text:
                        # 有的返回 chunks list
                        if "output" in data and isinstance(data["output"], list) and data["output"]:
                            # 拼接所有 text 字段
                            texts = [seg.get("text", "") for seg in data["output"] if isinstance(seg, dict)]
                            text = "\n".join(texts).strip()
                if not text:
                    self.logger.warning(f"Qwen API 无法找到文本字段: {str(data)[:120]}")
                    return None
                # 解析JSON
                json_str = None
                if '```json' in text:
                    s = text.find('```json') + 7
                    e = text.find('```', s)
                    json_str = text[s:e].strip()
                elif '{' in text and '}' in text:
                    json_str = text[text.find('{'):text.rfind('}')+1]
                if json_str:
                    try:
                        return json.loads(json_str)
                    except Exception:
                        self.logger.warning("Qwen API JSON解析失败，回退文本解析")
                return self._parse_text_response(text)
            else:
                self.logger.error(f"Qwen API 调用失败: {resp.status_code} {resp.text[:120]}")
                return None
        except Exception as e:
            self.logger.error(f"Qwen API 调用异常: {e}")
            return None

    def analyze_scene(self, image: np.ndarray) -> Optional[Dict]:
        """分析场景，返回感知结果"""
        if image is None:
            return None
        # 1. 云端Qwen优先
        image_base64_lazy = None
        if Config.USE_QWEN_API:
            # 需要 base64
            if image_base64_lazy is None:
                image_base64_lazy = self._encode_image_to_base64(image)
            qwen_api_result = self._call_qwen_api(image_base64_lazy)
            if qwen_api_result:
                self.logger.debug(f"Qwen API感知结果: {qwen_api_result}")
                return qwen_api_result
        # 2. 本地Qwen
        if Config.USE_QWEN:
            qwen_result = self._call_qwen_local(image)
            if qwen_result:
                self.logger.debug(f"Qwen本地感知结果: {qwen_result}")
                return qwen_result
        # 3. 远程OpenAI / HF
        if image_base64_lazy is None:
            image_base64_lazy = self._encode_image_to_base64(image)
        if Config.USE_OPENAI:
            result = self._call_openai_vision(image_base64_lazy)
        else:
            result = self._call_huggingface_api(image_base64_lazy)
        if result:
            self.logger.debug(f"感知结果: {result}")
        return result
    
    def close(self):
        """关闭摄像头"""
        if self.camera:
            self.camera.release()
            self.is_camera_open = False
            self.logger.info("摄像头已关闭")


class DecisionMaker:
    """决策模块"""
    
    def __init__(self, logger: Logger):
        self.logger = logger
        self.last_action_time = 0
        self.action_history = []
        
        # 决策提示模板
        self.decision_prompt = """
        基于以下场景感知信息，为机器人跟随任务决定下一步动作：
        
        感知信息: {perception_data}
        
        请返回JSON格式的动作指令：
        {{
            "action": "move/turn/stop/search",
            "params": {{
                "speed": 移动速度(m/s, 0-0.5),
                "distance": 移动距离(m) 或 "angle": 转向角度(rad, 负值左转),
                "duration": 动作持续时间(s)
            }},
            "reason": "决策原因",
            "confidence": 决策置信度(0.0-1.0)
        }}
        
        决策规则：
        1. 如果检测到目标人且在中心位置，向前移动保持安全距离
        2. 如果目标人在左侧或右侧，转向目标方向
        3. 如果检测到障碍物，停止或避让
        4. 如果未检测到目标，搜索模式（慢速转向）
        5. 保持1.5-2.0米的跟随距离
        """
    
    def _call_qwen_text(self, prompt: str) -> Optional[Dict]:
        """调用 Qwen 文本/多模态文本接口进行决策（只文本）"""
        if not Config.USE_QWEN_API or not Config.QWEN_API_KEY:
            return None
        headers = {
            "Content-Type": "application/json",
            "Authorization": f"Bearer {Config.QWEN_API_KEY}",
        }
        payload = {
            "model": Config.QWEN_API_MODEL,
            "input": [
                {
                    "role": "user",
                    "content": [
                        {"text": prompt}
                    ]
                }
            ],
            "parameters": {
                "max_tokens": 300,
                "temperature": 0.2
            }
        }
        try:
            resp = requests.post(Config.QWEN_API_URL, headers=headers, json=payload, timeout=15)
            if resp.status_code == 200:
                data = resp.json()
                text = (data.get("output", {}) or {}).get("text") or data.get("text")
                if not text and isinstance(data.get("output"), list):
                    texts = [seg.get("text", "") for seg in data["output"] if isinstance(seg, dict)]
                    text = "\n".join(texts).strip()
                if not text:
                    self.logger.warning("Qwen决策API未返回文本")
                    return None
                # 解析JSON
                json_str = None
                if '```json' in text:
                    s = text.find('```json') + 7
                    e = text.find('```', s)
                    json_str = text[s:e].strip()
                elif '{' in text and '}' in text:
                    json_str = text[text.find('{'):text.rfind('}')+1]
                if json_str:
                    try:
                        return json.loads(json_str)
                    except Exception:
                        self.logger.warning("Qwen决策JSON解析失败")
                return None
            else:
                self.logger.error(f"Qwen决策API失败: {resp.status_code} {resp.text[:100]}")
                return None
        except Exception as e:
            self.logger.error(f"Qwen决策API异常: {e}")
            return None

    def _call_decision_llm(self, perception_data: Dict) -> Optional[Dict]:
        """调用LLM进行决策"""
        prompt = self.decision_prompt.format(perception_data=json.dumps(perception_data, indent=2))
        # 优先顺序：Qwen API -> OpenAI -> 规则
        if Config.USE_QWEN_API:
            qwen_decision = self._call_qwen_text(prompt)
            if qwen_decision:
                return qwen_decision
        if Config.USE_OPENAI:
            return self._call_openai_text(prompt)
        return self._rule_based_decision(perception_data)
    
    def _call_openai_text(self, prompt: str) -> Optional[Dict]:
        """调用OpenAI文本模型进行决策"""
        headers = {
            "Content-Type": "application/json",
            "Authorization": f"Bearer {Config.OPENAI_API_KEY}"
        }
        
        payload = {
            "model": "gpt-4-turbo-preview",
            "messages": [{"role": "user", "content": prompt}],
            "max_tokens": 300
        }
        
        try:
            response = requests.post(Config.OPENAI_API_URL, headers=headers, json=payload, timeout=10)
            if response.status_code == 200:
                result = response.json()
                content = result['choices'][0]['message']['content']
                
                # 解析JSON
                try:
                    if '```json' in content:
                        json_start = content.find('```json') + 7
                        json_end = content.find('```', json_start)
                        json_str = content[json_start:json_end].strip()
                    elif '{' in content and '}' in content:
                        json_start = content.find('{')
                        json_end = content.rfind('}') + 1
                        json_str = content[json_start:json_end]
                    else:
                        json_str = content
                    
                    return json.loads(json_str)
                except json.JSONDecodeError:
                    self.logger.warning(f"无法解析决策JSON: {content}")
                    return None
            else:
                self.logger.error(f"OpenAI文本API调用失败: {response.status_code}")
                return None
        except Exception as e:
            self.logger.error(f"OpenAI文本API调用异常: {e}")
            return None
    
    def _rule_based_decision(self, perception_data: Dict) -> Dict:
        """基于规则的决策（后备方案）"""
        target = perception_data.get('target', {})
        obstacles = perception_data.get('obstacles', [])
        
        # 检查是否检测到目标
        if not target.get('detected', False):
            return {
                "action": "search",
                "params": {"speed": 0.1, "angle": 0.3, "duration": 2.0},
                "reason": "未检测到目标，进入搜索模式",
                "confidence": 0.8
            }
        
        # 检查障碍物
        if obstacles:
            return {
                "action": "stop",
                "params": {"duration": 1.0},
                "reason": f"检测到障碍物: {obstacles}",
                "confidence": 0.9
            }
        
        position = target.get('position', 'center')
        distance = target.get('distance', 2.0)
        
        # 距离太近，后退
        if distance < 1.0:
            return {
                "action": "move",
                "params": {"speed": -0.2, "distance": 0.5, "duration": 2.0},
                "reason": f"距离过近({distance:.1f}m)，后退",
                "confidence": 0.8
            }
        
        # 距离太远，前进
        elif distance > 3.0:
            return {
                "action": "move",
                "params": {"speed": 0.3, "distance": 1.0, "duration": 3.0},
                "reason": f"距离过远({distance:.1f}m)，前进",
                "confidence": 0.8
            }
        
        # 根据位置调整方向
        elif position == "left":
            return {
                "action": "turn",
                "params": {"speed": 0.2, "angle": -0.3, "duration": 1.5},
                "reason": "目标在左侧，左转",
                "confidence": 0.8
            }
        
        elif position == "right":
            return {
                "action": "turn",
                "params": {"speed": 0.2, "angle": 0.3, "duration": 1.5},
                "reason": "目标在右侧，右转",
                "confidence": 0.8
            }
        
        else:  # center position
            if distance > Config.SAFE_DISTANCE:
                return {
                    "action": "move",
                    "params": {"speed": 0.2, "distance": 0.3, "duration": 1.5},
                    "reason": f"目标在中心，距离{distance:.1f}m，缓慢前进",
                    "confidence": 0.9
                }
            else:
                return {
                    "action": "stop",
                    "params": {"duration": 1.0},
                    "reason": f"目标在中心，距离适当({distance:.1f}m)，保持位置",
                    "confidence": 0.9
                }
    
    def make_decision(self, perception_data: Dict) -> Optional[Dict]:
        """基于感知数据做出决策"""
        if not perception_data:
            return None
        
        # 首先尝试LLM决策
        decision = self._call_decision_llm(perception_data)
        
        # 如果LLM失败，使用规则决策
        if not decision:
            decision = self._rule_based_decision(perception_data)
        
        # 验证和修正决策参数
        if decision:
            decision = self._validate_decision(decision)
            
            # 记录决策历史
            self.action_history.append({
                'timestamp': time.time(),
                'perception': perception_data,
                'decision': decision
            })
            
            # 保持历史记录在合理长度
            if len(self.action_history) > 50:
                self.action_history = self.action_history[-50:]
            
            self.logger.info(f"决策: {decision['action']} - {decision['reason']}")
        
        return decision
    
    def _validate_decision(self, decision: Dict) -> Dict:
        """验证和修正决策参数"""
        action = decision.get('action', 'stop')
        params = decision.get('params', {})
        
        # 限制速度参数
        if 'speed' in params:
            if action in ['move', 'turn']:
                params['speed'] = max(-Config.MAX_SPEED, 
                                    min(Config.MAX_SPEED, params['speed']))
            elif action == 'turn':
                params['speed'] = max(-Config.MAX_TURN_SPEED, 
                                    min(Config.MAX_TURN_SPEED, params['speed']))
        
        # 限制距离和角度
        if 'distance' in params:
            params['distance'] = max(0.1, min(2.0, params['distance']))
        
        if 'angle' in params:
            params['angle'] = max(-1.57, min(1.57, params['angle']))  # ±90度
        
        # 设置默认持续时间
        if 'duration' not in params:
            params['duration'] = 1.0
        
        decision['params'] = params
        return decision


class ControlSignalGenerator:
    """控制信号生成模块"""
    
    def __init__(self, logger: Logger):
        self.logger = logger
        self.action_log = []
        self.is_pepper_connected = False
        
        # 动作执行状态
        self.current_action = None
        self.action_start_time = 0
        
    def execute_action(self, decision: Dict) -> bool:
        """执行动作决策"""
        if not decision:
            return False
        
        action = decision.get('action', 'stop')
        params = decision.get('params', {})
        reason = decision.get('reason', '')
        
        # 记录动作
        action_record = {
            'timestamp': datetime.now().isoformat(),
            'action': action,
            'params': params,
            'reason': reason
        }
        self.action_log.append(action_record)
        
        # 输出控制信号到控制台
        self._output_control_signal(action, params, reason)
        
        # 如果连接了Pepper，执行实际控制
        if self.is_pepper_connected:
            return self._execute_pepper_action(action, params)
        
        # 模拟执行
        self.current_action = decision
        self.action_start_time = time.time()
        
        return True
    
    def _output_control_signal(self, action: str, params: Dict, reason: str):
        """输出控制信号到控制台"""
        timestamp = datetime.now().strftime('%H:%M:%S.%f')[:-3]
        
        print(f"\n{'='*60}")
        print(f"[{timestamp}] 控制信号输出")
        print(f"{'='*60}")
        
        if action == 'move':
            speed = params.get('speed', 0)
            distance = params.get('distance', 0)
            if speed >= 0:
                print(f"🚶 前进控制: 速度 {speed:.2f} m/s, 距离 {distance:.2f} m")
            else:
                print(f"🚶 后退控制: 速度 {abs(speed):.2f} m/s, 距离 {distance:.2f} m")
                
        elif action == 'turn':
            speed = params.get('speed', 0)
            angle = params.get('angle', 0)
            direction = "左转" if angle < 0 else "右转"
            print(f"🔄 转向控制: {direction} {abs(angle):.2f} 弧度, 速度 {speed:.2f} rad/s")
            
        elif action == 'stop':
            print(f"🛑 停止控制: 机器人停止移动")
            
        elif action == 'search':
            angle = params.get('angle', 0)
            speed = params.get('speed', 0)
            print(f"🔍 搜索模式: 转向 {angle:.2f} 弧度, 速度 {speed:.2f} rad/s")
        
        print(f"📝 决策原因: {reason}")
        print(f"⏱️  执行时长: {params.get('duration', 1.0):.1f} 秒")
        print(f"{'='*60}\n")
        
        # 记录到日志
        self.logger.info(f"控制信号 - {action}: {params} - {reason}")
    
    def _execute_pepper_action(self, action: str, params: Dict) -> bool:
        """执行Pepper机器人实际控制（适配时启用）"""
        # 这里是Pepper机器人的实际控制代码
        # 需要NAOqi SDK支持
        
        try:
            # 示例代码（需要取消注释并安装NAOqi）
            """
            from naoqi import ALProxy
            
            motion_proxy = ALProxy("ALMotion", Config.PEPPER_IP, Config.PEPPER_PORT)
            
            if action == 'move':
                distance = params.get('distance', 0)
                speed = params.get('speed', 0.3)
                motion_proxy.moveTo(distance, 0, 0, speed)
                
            elif action == 'turn':
                angle = params.get('angle', 0)
                speed = params.get('speed', 0.2)
                motion_proxy.moveTo(0, 0, angle, speed)
                
            elif action == 'stop':
                motion_proxy.stopMove()
                
            return True
            """
            
            # 当前仅模拟
            self.logger.info(f"Pepper控制模拟: {action} with {params}")
            return True
            
        except Exception as e:
            self.logger.error(f"Pepper控制执行失败: {e}")
            return False
    
    def is_action_complete(self) -> bool:
        """检查当前动作是否完成"""
        if not self.current_action:
            return True
        
        duration = self.current_action.get('params', {}).get('duration', 1.0)
        elapsed = time.time() - self.action_start_time
        
        return elapsed >= duration
    
    def save_action_log(self, filename: Optional[str] = None):
        """保存动作日志到文件"""
        if not filename:
            filename = f"action_log_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
        
        try:
            with open(filename, 'w', encoding='utf-8') as f:
                json.dump(self.action_log, f, ensure_ascii=False, indent=2)
            self.logger.info(f"动作日志已保存到: {filename}")
        except Exception as e:
            self.logger.error(f"保存动作日志失败: {e}")
    
    def connect_pepper(self, ip: str = None, port: int = None) -> bool:
        """连接Pepper机器人（适配时使用）"""
        try:
            # 这里添加Pepper连接代码
            # 需要NAOqi SDK
            """
            from naoqi import ALProxy
            
            ip = ip or Config.PEPPER_IP
            port = port or Config.PEPPER_PORT
            
            # 测试连接
            motion_proxy = ALProxy("ALMotion", ip, port)
            motion_proxy.wakeUp()  # 唤醒机器人
            
            self.is_pepper_connected = True
            self.logger.info(f"成功连接到Pepper机器人: {ip}:{port}")
            return True
            """
            
            # 当前仅模拟连接
            self.logger.info("Pepper连接模拟成功")
            return False
            
        except Exception as e:
            self.logger.error(f"Pepper连接失败: {e}")
            return False


class RobotFollowingSystem:
    """机器人跟随系统主类"""
    
    def __init__(self):
        self.logger = Logger()
        self.perception = VLMPerception(self.logger)
        self.decision_maker = DecisionMaker(self.logger)
        self.controller = ControlSignalGenerator(self.logger)
        
        self.is_running = False
        self.frame_count = 0
        self.start_time = time.time()
        
        # 性能监控
        self.fps_counter = 0
        self.last_fps_time = time.time()
        
        # 状态显示窗口
        self.display_frame = None
        self.status_text = ""
        
    def start_system(self):
        """启动机器人跟随系统"""
        self.logger.info("启动机器人跟随系统...")
        
        # 检查API配置
        if Config.USE_OPENAI and Config.OPENAI_API_KEY == "your-api-key-here":
            self.logger.warning("未配置OpenAI API Key，将使用规则决策")
        
        # 显示系统信息
        self._display_system_info()
        
        self.is_running = True
        
        try:
            self._main_loop()
        except KeyboardInterrupt:
            self.logger.info("接收到中断信号，正在停止系统...")
        except Exception as e:
            self.logger.error(f"系统运行异常: {e}")
        finally:
            self._cleanup()
    
    def _display_system_info(self):
        """显示系统信息"""
        print("\n" + "="*80)
        print("🤖 基于VLM的机器人跟随系统")
        print("="*80)
        print(f"📷 摄像头: {Config.CAMERA_WIDTH}x{Config.CAMERA_HEIGHT} @ {Config.CAMERA_FPS}fps")
        print(f"🧠 VLM模型: {'OpenAI GPT-4 Vision' if Config.USE_OPENAI else 'Hugging Face LLaVA'}")
        print(f"🎯 跟随距离: {Config.SAFE_DISTANCE}m")
        print(f"⚡ 最大速度: {Config.MAX_SPEED}m/s")
        print("="*80)
        print("📋 控制说明:")
        print("  - 按 'q' 键退出系统")
        print("  - 按 's' 键保存动作日志") 
        print("  - 按 'p' 键连接Pepper机器人")
        print("  - 按 'r' 键重置系统状态")
        print("="*80)
        print("🚀 系统启动中...\n")
    
    def _main_loop(self):
        """主循环"""
        while self.is_running:
            loop_start_time = time.time()
            
            # 捕获图像
            frame = self.perception.capture_frame()
            if frame is None:
                time.sleep(0.1)
                continue
            
            self.frame_count += 1
            self.display_frame = frame.copy()
            
            # 添加状态信息到显示帧
            self._add_status_overlay(self.display_frame)
            
            # 显示图像
            cv2.imshow('Robot Following System', self.display_frame)
            
            # 处理键盘输入
            key = cv2.waitKey(1) & 0xFF
            if key == ord('q'):
                break
            elif key == ord('s'):
                self.controller.save_action_log()
            elif key == ord('p'):
                self.controller.connect_pepper()
            elif key == ord('r'):
                self._reset_system()
            
            # 控制处理频率
            if self.frame_count % max(1, int(Config.CAMERA_FPS * Config.FRAME_INTERVAL)) == 0:
                # 进行VLM分析和决策
                self._process_frame(frame)
            
            # 更新FPS
            self._update_fps()
            
            # 控制循环频率
            elapsed = time.time() - loop_start_time
            if elapsed < Config.FRAME_INTERVAL:
                time.sleep(Config.FRAME_INTERVAL - elapsed)
    
    def _process_frame(self, frame: np.ndarray):
        """处理单帧图像"""
        try:
            # 感知阶段
            perception_result = self.perception.analyze_scene(frame)
            if perception_result is None:
                self.status_text = "❌ VLM分析失败"
                return
            
            # 更新状态文本
            target = perception_result.get('target', {})
            if target.get('detected', False):
                pos = target.get('position', 'unknown')
                dist = target.get('distance', 0)
                self.status_text = f"🎯 目标: {pos}, {dist:.1f}m"
            else:
                self.status_text = "🔍 搜索目标中..."
            
            # 决策阶段
            decision = self.decision_maker.make_decision(perception_result)
            if decision is None:
                self.status_text += " | ❌ 决策失败"
                return
            
            # 控制阶段
            if self.controller.is_action_complete():
                success = self.controller.execute_action(decision)
                if success:
                    action = decision.get('action', 'unknown')
                    self.status_text += f" | ✅ {action}"
                else:
                    self.status_text += " | ❌ 控制失败"
            else:
                self.status_text += " | ⏳ 执行中..."
                
        except Exception as e:
            self.logger.error(f"帧处理异常: {e}")
            self.status_text = f"❌ 处理错误: {str(e)[:30]}"
    
    def _add_status_overlay(self, frame: np.ndarray):
        """在显示帧上添加状态信息"""
        height, width = frame.shape[:2]
        
        # 创建半透明覆盖层
        overlay = frame.copy()
        cv2.rectangle(overlay, (0, 0), (width, 120), (0, 0, 0), -1)
        cv2.addWeighted(overlay, 0.7, frame, 0.3, 0, frame)
        
        # 添加文本信息
        font = cv2.FONT_HERSHEY_SIMPLEX
        
        # 系统状态
        cv2.putText(frame, "Robot Following System", (10, 25), 
                   font, 0.7, (0, 255, 255), 2)
        
        # 运行时间
        runtime = time.time() - self.start_time
        cv2.putText(frame, f"Runtime: {runtime:.1f}s", (10, 50), 
                   font, 0.5, (255, 255, 255), 1)
        
        # FPS
        cv2.putText(frame, f"FPS: {self.fps_counter:.1f}", (10, 70), 
                   font, 0.5, (255, 255, 255), 1)
        
        # 状态文本
        if self.status_text:
            cv2.putText(frame, self.status_text[:50], (10, 95), 
                       font, 0.5, (0, 255, 0), 1)
        
        # 帧计数
        cv2.putText(frame, f"Frame: {self.frame_count}", (width-150, 25), 
                   font, 0.5, (255, 255, 255), 1)
        
        # 添加中心十字线（帮助调试目标位置）
        center_x, center_y = width // 2, height // 2
        cv2.line(frame, (center_x - 20, center_y), (center_x + 20, center_y), (0, 255, 0), 2)
        cv2.line(frame, (center_x, center_y - 20), (center_x, center_y + 20), (0, 255, 0), 2)
    
    def _update_fps(self):
        """更新FPS计数"""
        current_time = time.time()
        if current_time - self.last_fps_time >= 1.0:
            self.fps_counter = self.frame_count / (current_time - self.start_time)
            self.last_fps_time = current_time
    
    def _reset_system(self):
        """重置系统状态"""
        self.logger.info("重置系统状态...")
        self.frame_count = 0
        self.start_time = time.time()
        self.status_text = "🔄 系统已重置"
        
        # 清空历史记录
        self.decision_maker.action_history.clear()
        self.controller.action_log.clear()
    
    def _cleanup(self):
        """清理资源"""
        self.logger.info("正在清理系统资源...")
        
        # 保存最终日志
        self.controller.save_action_log()
        
        # 关闭摄像头
        self.perception.close()
        
        # 关闭OpenCV窗口
        cv2.destroyAllWindows()
        
        # 显示运行统计
        runtime = time.time() - self.start_time
        avg_fps = self.frame_count / runtime if runtime > 0 else 0
        
        print("\n" + "="*60)
        print("📊 系统运行统计")
        print("="*60)
        print(f"⏱️  总运行时间: {runtime:.1f} 秒")
        print(f"📸 处理帧数: {self.frame_count}")
        print(f"📈 平均FPS: {avg_fps:.1f}")
        print(f"🎬 动作记录数: {len(self.controller.action_log)}")
        print("="*60)
        print("✅ 系统已完全关闭")


def main():
    """主函数"""
    print("🤖 正在初始化机器人跟随系统...")
    
    # 检查依赖
    try:
        import cv2
        import requests
        print("✅ 依赖检查通过")
    except ImportError as e:
        print(f"❌ 缺少依赖: {e}")
        print("请运行: pip install opencv-python requests")
        return
    
    # 启动系统
    system = RobotFollowingSystem()
    system.start_system()


if __name__ == "__main__":
    main()
