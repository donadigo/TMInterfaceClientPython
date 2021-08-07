from tminterface.interface import TMInterface
from tminterface.client import Client, run_client
import sys

class MainClient(Client):
    def __init__(self) -> None:
        pass

    def on_registered(self, iface: TMInterface) -> None:
        print(f'Registered to {iface.server_name}')
        iface.register_custom_command('echo')

    def on_custom_command(self, iface, time_from: int, time_to: int, command: str, args: list):
        # Usage: echo [message] [severity]
        # echo "Something like this"
        # echo "An error message" error
        if command == 'echo':
            if len(args) > 0:
                severity = 'log' if len(args) == 1 else args[1]
                iface.log(args[0], severity)
            else:
                iface.log('echo takes at least one argument', 'error')


def main():
    server_name = f'TMInterface{sys.argv[1]}' if len(sys.argv) > 1 else 'TMInterface0'
    print(f'Connecting to {server_name}...')
    run_client(MainClient(), server_name)


if __name__ == '__main__':
    main()
