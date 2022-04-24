from tminterface.interface import TMInterface
from tminterface.client import Client
import sys

import time
import signal


class MainClient(Client):
    def __init__(self) -> None:
        super(MainClient, self).__init__()
        self.time = 0
        self.finished = False

    def on_registered(self, iface: TMInterface) -> None:
        print(f'Registered to {iface.server_name}')

    def on_deregistered(self, iface: TMInterface):
        print(f'Deregistered from {iface.server_name}')

    def on_run_step(self, iface: TMInterface, _time: int):
        self.time = _time

    def on_checkpoint_count_changed(self, iface: TMInterface, current: int, target: int):
        if current == target:
            self.finished = True


def main():
    server_name = f'TMInterface{sys.argv[1]}' if len(sys.argv) > 1 else 'TMInterface0'
    print(f'Connecting to {server_name}...')
    client = MainClient()
    iface = TMInterface(server_name)

    def handler(signum, frame):
        iface.close()
        quit()

    signal.signal(signal.SIGBREAK, handler)
    signal.signal(signal.SIGINT, handler)
    iface.register(client)

    while not iface.registered:
        time.sleep(0)

    last_finished = False
    last_time = 0
    while True:
        if last_finished != client.finished:
            last_finished = client.finished
            if last_finished:
                print('Finished')

        if client.time != last_time:
            last_time = client.time

            if client.time % 1000 == 0:
                print(client.time)
        time.sleep(0)


if __name__ == '__main__':
    main()