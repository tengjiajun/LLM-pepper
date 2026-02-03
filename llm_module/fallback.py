"""规则/本地回退"""


class LocalFallback:
	def __init__(self, function_actions):
		self.function_actions = function_actions

	def simple_text_correction(self, text):
		"""简单的本地文本纠错函数，处理常见拼写错误"""
		corrections = {
			"摔": "帅",
			"赵虎": "招呼",
			"守": "手",
			"跳哥舞": "跳个舞",
			"过的咋样": "过得怎么样",
		}
		corrected_text = text
		for wrong, right in corrections.items():
			corrected_text = corrected_text.replace(wrong, right)
		return corrected_text

	def local_action_match(self, text):
		"""本地动作匹配，基于纠错后的文本"""
		def _pick_value(spec):
			if not isinstance(spec, str):
				return None

			spec = spec.strip()
			default_value = None
			if "default" in spec:
				try:
					default_str = spec.split("default", 1)[1].strip()
					default_value = float(default_str)
				except Exception:
					default_value = None

			if spec.startswith("int(") and ")" in spec:
				inner = spec.split("int(", 1)[1].split(")", 1)[0]
				min_str, max_str = inner.split("-", 1)
				min_val, max_val = int(float(min_str)), int(float(max_str))
				if default_value is not None:
					return int(round(default_value))
				return int((min_val + max_val) // 2)

			if spec.startswith("float(") and ")" in spec:
				inner = spec.split("float(", 1)[1].split(")", 1)[0]
				min_str, max_str = inner.split("-", 1)
				min_val, max_val = float(min_str), float(max_str)
				if default_value is not None:
					return float(default_value)
				return float((min_val + max_val) / 2.0)

			return None

		for action in self.function_actions:
			describe = action["describe"]
			if describe in text or any(word in text for word in describe.split()):
				intent = action["intent"]
				module = action["module"]
				params = action["params"]
				# 为参数选择默认值（支持 int/float + default）
				if params:
					chosen_params = {}
					for k, v in params.items():
						chosen = _pick_value(v)
						if chosen is not None:
							chosen_params[k] = chosen
					if chosen_params:
						return {
							"group": [{"intent": intent, "module": module, "params": chosen_params}],
							"reply": f"没问题，我来{describe}！"
						}
				return {
					"group": [{"intent": intent, "module": module, "params": {}}],
					"reply": f"没问题，我来{describe}！"
				}
		return {"group": [], "reply": "抱歉，我不是很明白，请您再试试吧。"}