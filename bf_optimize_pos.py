from tminterface.structs import BFEvaluationDecision, BFEvaluationInfo, BFEvaluationResponse, BFPhase, BFTarget
from tminterface.interface import TMInterface
from tminterface.client import Client
import sys
import signal
import time

import numpy as np

# Example optimizing X position on A01-Race
class MainClient(Client):
    def __init__(self) -> None:
        self.current_time = 0
        self.do_accept = False
        self.force_accept = False
        self.lowest_time = 0
        self.phase = BFPhase.INITIAL

    def on_registered(self, iface: TMInterface) -> None:
        print(f'Registered to {iface.server_name}')
        iface.execute_command('set controller bruteforce')
        iface.execute_command('set bf_search_forever true')
    
    def on_simulation_begin(self, iface):
        self.lowest_time = iface.get_event_buffer().events_duration

    def on_bruteforce_evaluate(self, iface, info: BFEvaluationInfo) -> BFEvaluationResponse:
        self.current_time = info.time - 2610
        self.phase = info.phase

        response = BFEvaluationResponse()
        response.decision = BFEvaluationDecision.DO_NOTHING

        if (self.do_accept and self.current_ending_pos[0] < self.target_ending_pos[0]) or self.force_accept:
            print(self.current_ending_pos[0], self.target_ending_pos[0])
            response.decision = BFEvaluationDecision.ACCEPT
        elif self.current_time > self.lowest_time:
            response.decision = BFEvaluationDecision.REJECT
            self.current_ending_pos = self.target_ending_pos

        self.do_accept = False
        self.force_accept = False

        return response

    def on_checkpoint_count_changed(self, iface, current: int, target: int):
        if current == target:
            if self.phase == BFPhase.INITIAL:
                self.lowest_time = self.current_time
                self.target_ending_pos = iface.get_simulation_state().get_position()
            elif self.phase == BFPhase.SEARCH:
                self.current_ending_pos = iface.get_simulation_state().get_position()
                if self.current_time <= self.lowest_time:
                    self.do_accept = True

                if self.current_time < self.lowest_time:
                    self.force_accept = True

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
