from tminterface.interface import TMInterface
from tminterface.client import Client
import sys
import signal
import time

class MainClient(Client):
    def __init__(self) -> None:
        self.state = None
        self.finished = False
        self.simtime = 0

    def on_registered(self, iface: TMInterface) -> None:
        print(f'Registered to {iface.server_name}')

    def on_simulation_begin(self, iface):
        iface.remove_state_validation()
        self.finished = False

    def on_simulation_step(self, iface, _time: int):
        self.simtime = _time
        if self.simtime == 2600:
            self.state = iface.get_simulation_state()

        if self.finished:
            iface.rewind_to_state(self.state)
            self.finished = False

    def on_checkpoint_count_changed(self, iface, current: int, target: int):
        print(f'Reached checkpoint {current}/{target}')
        if current == target:
            print(f'Finished the race at {self.simtime - 2610}')
            self.finished = True
            iface.prevent_simulation_finish()

    def on_simulation_end(self, iface, result: int):
        print('Simulation finished')

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
