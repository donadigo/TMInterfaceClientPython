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
