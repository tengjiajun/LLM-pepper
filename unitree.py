import argparse
import os


def main():
    parser = argparse.ArgumentParser(description="LLM-pepper Unitree(宇树/宇数) 仿真执行端入口")
    parser.add_argument(
        "--backend",
        choices=["mock", "ros2"],
        default=os.getenv("UNITREE_BACKEND", "mock"),
        help="mock: 仅打印/模拟; ros2: 发布 /cmd_vel (需要 rclpy) ",
    )
    parser.add_argument(
        "--server-ip",
        default=os.getenv("SERVER_IP", "127.0.0.1"),
        help="Socket server IP (同 server.py)",
    )
    parser.add_argument(
        "--server-port",
        type=int,
        default=int(os.getenv("SERVER_PORT", "5556")),
        help="Socket server port (同 server.py)",
    )
    parser.add_argument(
        "--cmd-vel-topic",
        default=os.getenv("UNITREE_CMD_VEL_TOPIC", "/cmd_vel"),
        help="ROS2 cmd_vel topic (backend=ros2 时生效)",
    )
    args = parser.parse_args()

    os.environ["UNITREE_BACKEND"] = str(args.backend)
    os.environ["SERVER_IP"] = str(args.server_ip)
    os.environ["SERVER_PORT"] = str(args.server_port)
    os.environ["UNITREE_CMD_VEL_TOPIC"] = str(args.cmd_vel_topic)

    import unitree_module

    unitree_module.main()


if __name__ == "__main__":
    main()
