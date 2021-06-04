from tminterface.interface import TMInterface
from tminterface.client import Client
import sys
import signal
import time

class MainClient(Client):
    def __init__(self) -> None:
        self.state = None

    def on_registered(self, iface: TMInterface) -> None:
        print(f'Registered to {iface.server_name}')

    def on_run_step(self, iface: TMInterface, _time: int):
        if _time == 500:
            self.state = iface.get_simulation_state()

        if _time == 5000:
            iface.rewind_to_state(self.state)

def handler(signum, frame):
    iface.close()
    sys.exit(0)

def main():
    server_name = 'TMInterface0'
    if len(sys.argv) > 1:
        server_name = 'TMInterface' + str(sys.argv[1])

    print(f'Connecting to {server_name}...')

    iface = TMInterface(server_name)

    signal.signal(signal.SIGBREAK, handler)
    signal.signal(signal.SIGINT, handler)

    client = MainClient()
    iface.register(client)

    while True:
        time.sleep(0)

if __name__ == '__main__':
    main()
