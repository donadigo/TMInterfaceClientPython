from typing import Union

from tminterface.structs import BFEvaluationInfo, BFEvaluationResponse
import signal
import time


class Client(object):
    def __init__(self):
        pass

    def on_registered(self, iface):
        pass

    def on_deregistered(self, iface):
        pass

    def on_shutdown(self, iface):
        pass

    def on_run_step(self, iface, _time: int):
        pass

    def on_simulation_begin(self, iface):
        pass

    def on_simulation_step(self, iface, _time: int):
        pass
    
    def on_simulation_end(self, iface, result: int):
        pass

    def on_checkpoint_count_changed(self, iface, current: int, target: int):
        pass

    def on_laps_count_changed(self, iface, current: int):
        pass

    def on_custom_command(self, iface, time_from: int, time_to: int, command: str, args: list):
        pass

    def on_bruteforce_evaluate(self, iface, info: BFEvaluationInfo) -> Union[BFEvaluationResponse, None]:
        pass

def run_client(client: Client, server_name: str = 'TMInterface0'):
    """
    Connects to a server with the specified server name and registers the client instance.
    The function closes the connection on SIGBREAK and SIGINT signals and will block
    until the client is deregistered in any way.

    Args:
        client (Client): the client instance to register
        server_name (str): the server name to connect to, TMInterface0 by default
    """
    from .interface import TMInterface

    iface = TMInterface(server_name)

    def handler(signum, frame):
        iface.close()

    signal.signal(signal.SIGBREAK, handler)
    signal.signal(signal.SIGINT, handler)

    iface.register(client)

    while iface.running:
        time.sleep(0)

