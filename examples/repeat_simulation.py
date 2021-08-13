from tminterface.interface import TMInterface
from tminterface.client import Client, run_client
import sys


class MainClient(Client):
    def __init__(self) -> None:
        self.state = None
        self.finished = False
        self.simtime = 0
        super(MainClient, self).__init__()

    def on_registered(self, iface: TMInterface) -> None:
        print(f'Registered to {iface.server_name}')

    def on_simulation_begin(self, iface: TMInterface):
        iface.remove_state_validation()
        self.finished = False

    def on_simulation_step(self, iface: TMInterface, _time: int):
        self.simtime = _time
        if self.simtime == 2600:
            self.state = iface.get_simulation_state()

        if self.finished:
            iface.rewind_to_state(self.state)
            self.finished = False

    def on_checkpoint_count_changed(self, iface: TMInterface, current: int, target: int):
        print(f'Reached checkpoint {current}/{target}')
        if current == target:
            print(f'Finished the race at {self.simtime - 2610}')
            self.finished = True
            iface.prevent_simulation_finish()

    def on_simulation_end(self, iface, result: int):
        print('Simulation finished')


def main():
    server_name = f'TMInterface{sys.argv[1]}' if len(sys.argv) > 1 else 'TMInterface0'
    print(f'Connecting to {server_name}...')
    run_client(MainClient(), server_name)


if __name__ == '__main__':
    main()
