
from .structs import BFEvaluationInfo, BFEvaluationResponse
class Client(object):
    def __init__(self):
        pass

    def on_registered(self, iface):
        pass

    def on_deregistered(self, iface):
        pass

    def on_shutdown(self, iface):
        pass

    def on_run_step(self, iface, time: int):
        pass

    def on_simulation_begin(self, iface):
        pass

    def on_simulation_step(self, iface, time: int):
        pass
    
    def on_simulation_end(self, iface, result: int):
        pass

    def on_checkpoint_count_changed(self, iface, current: int, target: int):
        pass

    def on_laps_count_changed(self, iface, current: int):
        pass

    def on_custom_command(self, iface, time_from: int, time_to: int, command: str, args: list):
        pass

    def on_bruteforce_evaluate(self, iface, info: BFEvaluationInfo) -> BFEvaluationResponse:
        return None