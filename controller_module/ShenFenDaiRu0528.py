import json
import re
import socket
import threading
from openai import OpenAI

# 使用用户提供的动作库
FUNCTION_ACTIONS = [
    {
        "intent": "wave_hand",
        "module": "active_1",
        "describe": "挥动右手，打个招呼",
        "params": {"angle": "int(30-90)"}
    },
    {
        "intent": "start_nod",
        "module": "head",
        "describe": "点一点头",
        "params": {"times": "int(1-5)"}
    },
    {
        "intent": "spin_around",
        "module": "move",
        "describe": "原地顺时针转圈",
        "params": {"times": "int(1-3)"}
    },
    {
        "intent": "enroll",
        "module": "sound",
        "describe": "注册名称,文本中会含有'enroll'和用户自我介绍,文本固定返回'hello,{name},很高兴认识你！'",
        "params": {"name": "str(用户姓名)"}
    },
    {
        "intent": "forget_name",
        "module": "sound",
        "describe": "忘记某人的信息",
        "params": {"name": "str(用户姓名)"}
    },
    {
        "intent": "clean_all_name",
        "module": "sound",
        "describe": "清除所有已注册的名称",
        "params": {}
    },
    {
        "intent": "name_list",
        "module": "sound",
        "describe": "列出所有已注册的人名",
        "params": {}
    },
    {
        "intent": "follow_me",
        "module": "sound",
        "describe": "跟随我,当用户走动时跟随用户,单位cm",
        "params": {"name": "str(用户姓名)","distance": "int(100-500)default 300"}
    },
    {
        "intent": "bow",
        "module": "body",
        "describe": "弯腰,鞠躬",
        "params": {}
    },
    {
        "intent": "dance1",
        "module": "body",
        "describe": "胡桃夹子舞蹈",
        "params": {}
    },
    {
        "intent": "tray_pose",
        "module": "active_2",
        "describe": "托盘动作：双手摆成托盘姿势并保持",
        "params": {}
    },
    {
        "intent": "left_spin_rotate",
        "module": "move",
        "describe": "左转指定角度（单位：度）",
        "params": {"degrees": "int(10-180)default 90"}
    },
    {
        "intent": "right_spin_rotate",
        "module": "move",
        "describe": "右转指定角度（单位：度）",
        "params": {"degrees": "int(10-180)default 90"}
    },
    {
        "intent": "forward",
        "module": "move",
        "describe": "前进指定距离（单位：米）",
        "params": {"distance": "float(0.1-10.0)default 1.0"}
    },
    {
        "intent": "retreat",
        "module": "move",
        "describe": "后退指定距离（单位：米）",
        "params": {"distance": "float(0.1-10.0)default 1.0"}
    },
    {
        "intent": "handshake",
        "module": "active_1",
        "describe": "握手，和说话人握手",
        "params": {}
    },
    {
        "intent": "shy",
        "module": "body",
        "describe": "当被表达喜爱、羡慕时害羞",
        "params": {}
    },
    {
        "intent": "proud",
        "module": "body",
        "describe": "当被夸赞时自豪",
        "params": {}
    },
    {
        "intent": "think",
        "module": "body",
        "describe": "思考,当用户向你问一些比较专业的问题时思考",
        "params": {}
    },
    {
        "intent": "salute",
        "module": "body",
        "describe": "敬礼",
        "params": {}
    },
    {
        "intent": "modify_action",
        "module": "body",
        "describe": "稍微调整动作,包括抬高或降低某个部位,如左臂、右臂、头等",
        "params": {"json": "str(需加引号，格式为{\"LShoulderPitch\": 0.1},表示抬高左臂0.1弧度)，{\"LElbowRoll\": 0.2},表示左肘弯曲程度加上0.2弧度，负数代表伸直)，{\"HeadPitch\": 0.2},表示头低0.2弧度，负数代表抬高"}
    },
    {
        "intent": "play_again",
        "module": "body",
        "describe": "重新执行上一个动作",
        "params": {}
    },
    {
        "intent": "save_action",
        "module": "body",
        "describe": "保存当前动作,以便后续调用(用户一般会提供名字,没提供名字时不需要提供参数，并询问用户刚才的动作名称)",
        "params": {"action_name": "str(动作名称，需加引号,若用户提供的名称是中文，则需要转换为英文，如“举手”转换为“raise_hand”，若用户没有提供名称，则不需要提供参数)"}
    }
]

class PepperServer:
    def __init__(self, host="localhost", port=5566, api_key="sk-32e369888c6a48f1918d0f2e0b3488a1", base_url="https://dashscope.aliyuncs.com/compatible-mode/v1"):
        self.host = host
        self.port = port
        self.server_socket = None
        self.running_event = threading.Event()
        self.json_cache = []  # 缓存 API 处理结果
        self.client = OpenAI(api_key=api_key, base_url=base_url)
        # 定义关键词列表，用于过滤与小朋友的交流
        self.ignore_keywords = []  # 可根据需要扩展
        self.system_message = {
            "role": "system",
            "content": (
                "你是一个智能助手，名叫小包同学，来自浙江工业大学，擅长处理语音识别的文本纠错、语义匹配和自然对话。用户输入了一段可能包含识别错误的语音命令或聊天文本，你需要完成以下任务：\n\n"
                "1. 将输入文本智能调整为正确的、自然的中文，记录纠错后的命令文本。例如，输入“我今天摔吗”调整为“我今天帅吗”，输入“打个赵虎”调整为“打个招呼”。\n"
                "2. 基于纠错后的命令，判断用户意图：\n"
                "   - 如果是请求Pepper执行动作，分析纠错后的命令，识别其中包含的一个或多个动作请求。特别注意：你必须参考以下动作列表中每个动作的 describe 字段，尤其是 describe 中描述的情境或触发条件（例如‘当被夸聪明、帅、美时感到自豪’）。具体步骤：\n"
                "     - 对于每个动作的 describe，检查纠错后的命令是否在语义上满足 describe 的动作描述或情境条件。例如，如果命令是‘你好帅’‘你好聪明’，应匹配到 describe 为‘自豪,当被夸时自豪’的动作，因为输入表示夸奖;如果命令是‘喜欢你’‘羡慕你’等表示喜爱的词，应匹配到 describe 为‘害羞’的动作。\n"
                "     - 优先考虑 describe 中包含情境描述的动作（例如‘当...时’），通过语义分析判断输入是否触发该情境。\n"
                "     - 动作列表为：\n"
                f"       {json.dumps(FUNCTION_ACTIONS, ensure_ascii=False)}\n"
                "   - 如果是正常聊天交流（非动作请求，例如日常问候或闲聊），直接生成与纠错后命令内容相关的友好、自然的回复，不涉及动作库。\n"
                "3. 处理动作请求：\n"
                "   - 对于每个识别到的动作请求，如果找到语义上基本相似的 describe，从对应的 params 字段的范围约束中选择合适的值：\n"
                "     - int(min-max)：选择范围内的整数；float(min-max)：选择范围内的小数。\n"
                "     - 若包含 default X，优先使用 default；否则选择中间值。\n"
                "     - move 模块单位要求：forward/retreat 的 distance 单位为米（float），left_spin_rotate/right_spin_rotate 的 degrees 单位为度（int）。follow_me 的 distance 单位为厘米（int）。\n"
                "     - 关键规则（必须遵守）：如果用户在纠错后的命令里明确说出了数值和单位（例如“前进5米”“后退2.5米”“左转90度”“右转45°”），则必须直接把该数值写入 params（必要时截断到允许范围），不要使用 default 或中间值替代。\n"
                "   - 将每个动作转换为一个JSON对象，包含 intent、module 和 params（params 使用具体值）。\n"
                "   - 将所有动作JSON组合成一个组（group）。\n"
                "   - 如果动作请求无法与任何 describe 匹配，返回空组，并附带回复：“抱歉，我不是很明白，请您再试试吧。”\n"
                "4. 处理聊天交流：\n"
                "   - 如果纠错后的命令是正常聊天，生成清爽、友好的回复，语气要活泼、自然，贴合纠错后命令的内容，避免机械化用词（如‘好的’）。\n"
                "5. 生成回复（reply）：\n"
                "   - 所有回复必须严格基于纠错后的命令生成，反映纠错后的语义。\n"
                "   - 禁止在回复中引用或回应原始输入中的任何错误词汇，只能使用纠错后的词汇。\n"
                "   - 对于动作请求，生成与动作和纠错后命令相关的活泼回复，语气友好，贴合上下文，避免在回复中出现‘我帮你xx’‘让’等词汇。特别地：\n"
                "     - 如果动作的 intent 是 'wave_hand'，回复可以灵活、自然，不受字数限制，基于 describe 字段生成贴合语义的回复。\n"
                "     - 对于其他动作（intent 不是 'wave_hand'），回复必须控制在8个字以内，语气活泼，基于 describe 字段生成简洁且贴合语义的回复。\n"
                "   - 对于聊天交流，生成与纠错后命令内容相关的自然对话，无字数限制。\n"
                "   - 确保回复避免以‘好的’开头，语气多样化。\n"
                "6. 返回格式：\n"
                "   - 动作请求（匹配成功）：\n"
                "     {\n"
                "       \"group\": [\n"
                "         {\"intent\": \"意图名称\", \"module\": \"模块名称\", \"params\": {\"参数名\": 具体值}},\n"
                "         ...\n"
                "       ],\n"
                "       \"reply\": \"动作相关回复\"\n"
                "     }\n"
                "   - 动作请求（无匹配）：\n"
                "     {\n"
                "       \"group\": [],\n"
                "       \"reply\": \"抱歉，我不是很明白，请您再试试吧。\"\n"
                "     }\n"
                "   - 正常聊天：\n"
                "     {\n"
                "       \"group\": [],\n"
                "       \"reply\": \"聊天回复\"\n"
                "     }\n"
                "7. 注意事项：\n"
                "   - 即使输入包含严重拼写错误，也要尽力纠错并返回有效JSON输出。\n"
                "   - 你的名字就是小包，不要说自己是什么pepper，你只能自称小包。\n"
                "   - 语义相似度比较基于纠错后的命令与 describe 的语义内容（包括情境描述），而非简单字符串匹配。\n"
                "   - 对于 params 的范围约束（如 'int(30-90)'、'float(0.1-3.0)'），选择合理值（优先 default，其次中间值）。\n"
                "   - 回复语气要活泼、友好，避免机械化表达（如‘好的’），确保自然流畅。\n"
                "   - 当识别到修改动作时（如‘稍微调整动作’），可调整的参数有：'HeadPitch', 'LShoulderPitch', 'LShoulderRoll', 'LElbowRoll', 'RShoulderPitch', 'RShoulderRoll', 'RElbowRoll',其中ElbowRoll是指大臂和小臂间的夹角\n"
            )
        }

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

        for action in FUNCTION_ACTIONS:
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
            response = self.client.chat.completions.create(
                model="qwen-turbo",
                messages=messages,
                stream=False
            )
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
            corrected_text = self.simple_text_correction(raw_text)
            if corrected_text != raw_text:
                print(f"本地纠错结果: {corrected_text}")
                result = self.local_action_match(corrected_text)
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

    def start(self):
        """启动服务器"""
        try:
            self.server_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            self.server_socket.bind((self.host, self.port))
            self.server_socket.listen(1)
            self.running_event.set()
            print(f"Pepper控制服务器已启动，监听在 {self.host}:{self.port}")

            while self.running_event.is_set():
                try:
                    self.server_socket.settimeout(1.0)  # 设置超时以检查 running_event
                    client_socket, address = self.server_socket.accept()
                    print(f"收到来自 {address} 的连接")
                    
                    # 接收数据
                    data = client_socket.recv(1024).decode('utf-8')
                    print(f"收到命令: {data}")
                    
                    # 处理命令并获取 API 响应
                    response = self.process_command(data)
                    
                    # 发送响应给客户端（序列化为 JSON 字符串）
                    client_socket.send(json.dumps(response, ensure_ascii=False).encode('utf-8'))
                    client_socket.close()
                    
                except socket.timeout:
                    continue
                except Exception as e:
                    print(f"处理客户端连接时出错: {str(e)}")
                    
        except Exception as e:
            print(f"服务器启动失败: {str(e)}")
        finally:
            self.stop()

    def stop(self):
        """停止服务器"""
        self.running_event.clear()
        if self.server_socket:
            self.server_socket.close()
            print("Pepper控制服务器已停止")
            print(f"最终缓存内容: {json.dumps(self.json_cache, ensure_ascii=False, indent=2)}")

def main():
    # 创建并启动 Pepper 服务器
    pepper_server = PepperServer()
    server_thread = threading.Thread(target=pepper_server.start)
    server_thread.start()

    # 保持程序运行，直到用户输入 'exit' 或 Ctrl+C
    try:
        while True:
            user_input = input("输入 'exit' 退出程序: ")
            if user_input.lower() == "exit":
                pepper_server.stop()
                break
            response = pepper_server.process_command(user_input)
            print(f"处理控制台输入结果: {response}")
    except KeyboardInterrupt:
        print("收到中断信号，正在停止服务器...")
        pepper_server.stop()
    finally:
        server_thread.join()  # 等待线程结束

if __name__ == "__main__":
    main()