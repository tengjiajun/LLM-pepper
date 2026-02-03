"""动作协议/校验"""

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
		"params": {"name": "str(用户姓名)", "distance": "int(100-500)default 300"}
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