"""LLM 调用封装"""

from openai import OpenAI


class LLMClient:
	def __init__(self, api_key, base_url, model="qwen-turbo"):
		self.client = OpenAI(api_key=api_key, base_url=base_url)
		self.model = model

	def chat(self, messages, stream=False):
		return self.client.chat.completions.create(
			model=self.model,
			messages=messages,
			stream=stream
		)