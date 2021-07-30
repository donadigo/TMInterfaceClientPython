from tminterface.interface import TMInterface
from tminterface.client import Client
import sys
import signal
import time

class MainClient(Client):
    def __init__(self) -> None:
        pass

    def on_registered(self, iface: TMInterface) -> None:
        print(f'Registered to {iface.server_name}')
        iface.register_custom_command('custom')

    def on_run_step(self, iface: TMInterface, _time: int):
        if _time >= 0:
            state = iface.get_simulation_state()

            speed = state.get_display_speed()
            vel = state.get_velocity()
            pos = state.get_position()
            aim = state.get_aim_direction()
            # print(f'Time: {_time}, Display Speed: {speed}, Position: {pos}, Velocity: {vel}, Aim Direction: {aim}')

    def on_custom_command(self, iface, time_from: int, time_to: int, command: str, args: list):
        print(time_from, time_to)
        print(command)
        print(args)

def main():
    server_name = 'TMInterface0'
    if len(sys.argv) > 1:
        server_name = 'TMInterface' + str(sys.argv[1])

    print(f'Connecting to {server_name}...')

    iface = TMInterface(server_name)
    def handler(signum, frame):
        iface.close()

    signal.signal(signal.SIGBREAK, handler)
    signal.signal(signal.SIGINT, handler)

    client = MainClient()
    iface.register(client)

    while iface.running:
        time.sleep(0)

if __name__ == '__main__':
    main()
