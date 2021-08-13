from tminterface.interface import TMInterface
from tminterface.client import Client, run_client
import sys


class MainClient(Client):
    def __init__(self) -> None:
        self.state = None
        super(MainClient, self).__init__()

    def on_registered(self, iface: TMInterface) -> None:
        print(f'Registered to {iface.server_name}')

    def on_run_step(self, iface: TMInterface, _time: int):
        if _time == 1000:
            iface.set_input_state(right=True, accelerate=True, brake=True)

        if _time == 500:
            self.state = iface.get_simulation_state()

        if _time == 5000:
            iface.rewind_to_state(self.state)


def main():
    server_name = f'TMInterface{sys.argv[1]}' if len(sys.argv) > 1 else 'TMInterface0'
    print(f'Connecting to {server_name}...')
    run_client(MainClient(), server_name)


if __name__ == '__main__':
    main()
