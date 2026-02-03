"""意图解析与分发"""

import json
import re

from .client import LLMClient
from .fallback import LocalFallback
from .prompts import build_system_message
from .schema import FUNCTION_ACTIONS


class LLMRouter:
	def __init__(self, api_key, base_url, model="qwen-turbo", function_actions=None):
		self.function_actions = function_actions or FUNCTION_ACTIONS
		self.client = LLMClient(api_key=api_key, base_url=base_url, model=model)
		self.fallback = LocalFallback(self.function_actions)
		self.system_message = build_system_message(self.function_actions)
		self.json_cache = []
		# 定义关键词列表，用于过滤与小朋友的交流
		self.ignore_keywords = []

	def process_command(self, raw_text):
		"""处理语音命令，调用通义千问 Qwen-turbo API，并缓存结果"""
		# 检查是否包含忽略关键词
		for keyword in self.ignore_keywords:
			if keyword in raw_text:
				result = {"group": [], "reply": ""}
				self.json_cache.append(result)
				print(f"检测到关键词 '{keyword}'，返回空结果并缓存: {result}")
				return result

		try:
			messages = [
				self.system_message,
				{"role": "user", "content": raw_text}
			]
			response = self.client.chat(messages=messages, stream=False)
			cleaned_json = response.choices[0].message.content.replace("```json", "").replace("```", "").strip()
			result = json.loads(cleaned_json)  # 解析为 Python 字典

			# 后处理：从原始文本中抽取“X米/X度”并覆盖默认值
			result = self._postprocess_move_params(raw_text, result)

			# 缓存处理结果
			self.json_cache.append(result)
			print(f"已缓存结果: {result}")
			return result
		except Exception as e:
			print(f"通义千问 API 处理错误: {str(e)}")
			print("请参考文档：https://help.aliyun.com/zh/model-studio/developer-reference/error-code")
			# 尝试本地处理
			corrected_text = self.fallback.simple_text_correction(raw_text)
			if corrected_text != raw_text:
				print(f"本地纠错结果: {corrected_text}")
				result = self.fallback.local_action_match(corrected_text)
			else:
				result = {"group": [], "reply": "抱歉，我听不太懂您的话，能再说一遍吗？"}

			# 本地/异常路径也做同样的参数后处理
			result = self._postprocess_move_params(corrected_text, result)
			# 缓存错误结果
			self.json_cache.append(result)
			print(f"已缓存错误结果: {result}")
			return result

	def _postprocess_move_params(self, text, result):
		try:
			if not isinstance(result, dict):
				return result
			group = result.get("group")
			if not isinstance(group, list) or not group:
				return result

			# 仅处理 move 模块四个意图
			distance_match = re.search(r"(\d+(?:\.\d+)?)\s*米", text)
			degree_match = re.search(r"(\d+(?:\.\d+)?)\s*(?:度|°)", text)

			for item in group:
				if not isinstance(item, dict):
					continue
				if item.get("module") != "move":
					continue
				intent = item.get("intent")
				params = item.get("params")
				if not isinstance(params, dict):
					params = {}
					item["params"] = params

				if intent in ("forward", "retreat") and distance_match:
					value = float(distance_match.group(1))
					# 与动作库保持一致：0.1-5.0
					value = max(0.1, min(5.0, value))
					params["distance"] = value

				if intent in ("left_spin_rotate", "right_spin_rotate") and degree_match:
					value = float(degree_match.group(1))
					value = int(round(value))
					# 与动作库保持一致：10-180
					value = max(10, min(180, value))
					params["degrees"] = value

			return result
		except Exception:
			return result