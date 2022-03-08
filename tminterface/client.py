
from tminterface.structs import BFEvaluationInfo, BFEvaluationResponse
from tminterface.constants import DEFAULT_SERVER_SIZE
import signal
import time


class Client(object):
    def __init__(self):
        pass

    def on_registered(self, iface):
        """
        A callback that the client has registered to a TMInterface instance.

        Args:
            iface (TMInterface): the TMInterface object that has been registered
        """
        pass

    def on_deregistered(self, iface):
        """
        A callback that the client has been deregistered from a TMInterface instance.
        This can be emitted when the game closes, the client does not respond in the timeout window,
        or the user manually deregisters the client with the `deregister` command.

        Args:
            iface (TMInterface): the TMInterface object that has been deregistered
        """
        pass

    def on_shutdown(self, iface):
        """
        A callback that the TMInterface server is shutting down. This is emitted when the game is closed.

        Args:
            iface (TMInterface): the TMInterface object that has been closed
        """
        pass

    def on_run_step(self, iface, _time: int):
        """
        Called on each "run" step (physics tick). This method will be called only in normal races and not
        when validating a replay.

        Args:
            iface (TMInterface): the TMInterface object
        """
        pass

    def on_simulation_begin(self, iface):
        """
        Called when a new simulation session is started (when validating a replay).

        Args:
            iface (TMInterface): the TMInterface object
        """
        pass

    def on_simulation_step(self, iface, _time: int):
        """
        Called on each simulation step (physics tick). This method will be called only when validating a replay.

        Args:
            iface (TMInterface): the TMInterface object
        """
        pass
    
    def on_simulation_end(self, iface, result: int):
        """
        Called when a new simulation session is ended (when validating a replay).

        Args:
            iface (TMInterface): the TMInterface object
        """
        pass

    def on_checkpoint_count_changed(self, iface, current: int, target: int):
        """
        Called when the current checkpoint count changed (a new checkpoint has been passed by the vehicle).
        The `current` and `target` parameters account for the total amount of checkpoints to be collected,
        taking lap count into consideration.

        Args:
            iface (TMInterface): the TMInterface object
            current (int): the current amount of checkpoints passed
            target (int): the total amount of checkpoints on the map (including finish)
        """
        pass

    def on_laps_count_changed(self, iface, current: int):
        """
        Called when the current lap count changed (a new lap has been passed).

        Args:
            iface (TMInterface): the TMInterface object
            current (int): the current amount of laps passed
        """
        pass

    def on_custom_command(self, iface, time_from: int, time_to: int, command: str, args: list):
        """
        Called when a custom command has been executed by the user.

        Args:
            iface (TMInterface): the TMInterface object
            time_from (int): if provided by the user, the starting time of the command, otherwise -1
            time_to (int): if provided by the user, the ending time of the command, otherwise -1
            command (str): the command name being executed
            args (list): the argument list provided by the user
        """
        pass

    def on_bruteforce_evaluate(self, iface, info: BFEvaluationInfo) -> BFEvaluationResponse:
        """
        Called on each bruteforce physics step iteration. This method will only be called when
        the bruteforce script is enabled in TMInterface. Used for implementing custom evaluation
        strategies. For greater control over the simulation, use the Client.on_simulation_step method instead.

        Args:
            iface (TMInterface): the TMInterface object
            info (BFEvaluationInfo): the info about the current bruteforce settings and race time

        Returns:
            None if the bruteforce script should continue its builtin evaluation or a BFEvaluationResponse
            that signifies what the script should do.
        """
        return None

    def on_client_exception(self, iface, exception: Exception):
        """
        Called when a client exception is thrown. This can happen if opening the shared file fails, or reading from
        it fails.

        Args:
            iface (TMInterface): the TMInterface object
            exception (Exception): the exception being thrown
        """
        print(f'[Client] Exception reported: {exception}')


def run_client(client: Client, server_name: str = 'TMInterface0', buffer_size=DEFAULT_SERVER_SIZE):
    """
    Connects to a server with the specified server name and registers the client instance.
    The function closes the connection on SIGBREAK and SIGINT signals and will block
    until the client is deregistered in any way. You can set the buffer size yourself to use for
    the connection, by specifying the buffer_size parameter. Using a custom size requires
    launching TMInterface with the /serversize command line parameter: TMInterface.exe /serversize=size.

    Args:
        client (Client): the client instance to register
        server_name (str): the server name to connect to, TMInterface0 by default
        buffer_size (int): the buffer size to use, the default size is defined by tminterface.constants.DEFAULT_SERVER_SIZE
    """
    from .interface import TMInterface

    iface = TMInterface(server_name, buffer_size)

    def handler(signum, frame):
        iface.close()

    signal.signal(signal.SIGBREAK, handler)
    signal.signal(signal.SIGINT, handler)

    iface.register(client)

    while iface.running:
        time.sleep(0)

