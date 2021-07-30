from tminterface.structs import BFEvaluationDecision, BFEvaluationInfo, BFEvaluationResponse, BFPhase
from tminterface.interface import TMInterface
from tminterface.client import Client
import sys
import signal
import time

import numpy as np

class MainClient(Client):
    def __init__(self) -> None:
        self.current_time = 0
        self.do_accept = False
        self.lowest_time = 0
        self.current_speeds = []
        self.target_speeds = []
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

        if self.current_time >= 10:
            state = iface.get_simulation_state()
            if self.phase == BFPhase.INITIAL:
                if self.current_time == 10:
                    self.target_speeds = []

                self.target_speeds.append(np.linalg.norm(state.get_velocity()))
            
            else:
                index = int((self.current_time - 10) / 10)
                if index < len(self.current_speeds):
                    self.current_speeds[index] = np.linalg.norm(state.get_velocity())

        if self.do_accept and sum(self.current_speeds) > sum(self.target_speeds):
            print(sum(self.current_speeds), sum(self.target_speeds))
            response.decision = BFEvaluationDecision.ACCEPT
        elif self.current_time > self.lowest_time:
            response.decision = BFEvaluationDecision.REJECT
            self.current_speeds = self.target_speeds[:]

        self.do_accept = False

        return response

    def on_checkpoint_count_changed(self, iface, current: int, target: int):
        if current == target:
            if self.phase == BFPhase.INITIAL:
                self.current_speeds = self.target_speeds[:]
                self.lowest_time = self.current_time
            elif self.phase == BFPhase.SEARCH:
                if self.current_time <= self.lowest_time:
                    self.do_accept = True

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
