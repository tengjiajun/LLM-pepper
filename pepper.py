import argparse
import os


def main():
	parser = argparse.ArgumentParser(description="LLM-pepper 执行端启动")
	parser.add_argument(
		"--mode",
		choices=["real", "sim"],
		default=os.getenv("PEPPER_MODE", "real"),
		help="切换真实 Pepper / 虚拟 Pepper(qiBullet)",
	)
	parser.add_argument(
		"--ip",
		default=None,
		help="真实 Pepper IP（默认使用 util/Config.py 里的 PEPPER_IP）",
	)
	parser.add_argument(
		"--sim-gui",
		action="store_true",
		help="仿真模式开启 GUI（默认开）",
	)
	parser.add_argument(
		"--sim-nogui",
		action="store_true",
		help="仿真模式关闭 GUI",
	)
	args = parser.parse_args()

	os.environ["PEPPER_MODE"] = args.mode
	if args.sim_nogui:
		os.environ["PEPPER_SIM_GUI"] = "0"
	elif args.sim_gui:
		os.environ["PEPPER_SIM_GUI"] = "1"

	if args.ip:
		# pepper_module 使用 `from util.Config import *`，所以要在 import 之前改
		from util import Config as _config

		_config.PEPPER_IP = args.ip

	import pepper_module  # noqa: F401


if __name__ == "__main__":
	main()