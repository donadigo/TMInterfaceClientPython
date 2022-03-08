import struct
import threading
import time
import mmap
from typing import Tuple

from tminterface.client import Client
from tminterface.structs import BFEvaluationResponse, BFEvaluationInfo, BFPhase, BFTarget, CheckpointData, SimStateData
from tminterface.eventbuffer import EventBufferData, Event
from tminterface.constants import *
from enum import IntEnum, auto


class MessageType(IntEnum):
    S_RESPONSE = auto()
    S_ON_REGISTERED = auto()
    S_SHUTDOWN = auto()
    S_ON_RUN_STEP = auto()
    S_ON_SIM_BEGIN = auto()
    S_ON_SIM_STEP = auto()
    S_ON_SIM_END = auto()
    S_ON_CHECKPOINT_COUNT_CHANGED = auto()
    S_ON_LAPS_COUNT_CHANGED = auto()
    S_ON_CUSTOM_COMMAND = auto()
    S_ON_BRUTEFORCE_EVALUATE = auto()
    C_REGISTER = auto()
    C_DEREGISTER = auto()
    C_PROCESSED_CALL = auto()
    C_SET_INPUT_STATES = auto()
    C_RESPAWN = auto()
    C_GIVE_UP = auto()
    C_HORN = auto()
    C_SIM_REWIND_TO_STATE = auto()
    C_SIM_GET_STATE = auto()
    C_SIM_GET_EVENT_BUFFER = auto()
    C_GET_CONTEXT_MODE = auto()
    C_SIM_SET_EVENT_BUFFER = auto()
    C_SIM_SET_TIME_LIMIT = auto()
    C_GET_CHECKPOINT_STATE = auto()
    C_SET_CHECKPOINT_STATE = auto()
    C_SET_GAME_SPEED = auto()
    C_EXECUTE_COMMAND = auto()
    C_SET_EXECUTE_COMMANDS = auto()
    C_SET_TIMEOUT = auto()
    C_REMOVE_STATE_VALIDATION = auto()
    C_PREVENT_SIMULATION_FINISH = auto()
    C_REGISTER_CUSTOM_COMMAND = auto()
    C_LOG = auto()
    ANY = auto()


RESPONSE_TOO_LONG = 1
CLIENT_ALREADY_REGISTERED = 2
NO_EVENT_BUFFER = 3
NO_PLAYER_INFO = 4
COMMAND_ALREADY_REGISTERED = 5

MAXINT32 = 2 ** 31 - 1


class Message(object):
    """
    The Message class represents a binary buffer that contains useful methods to construct
    a message to send to the server. A message additionally contains its type, whether it is
    a response to a server call, or a normal client call. It also contains an error code,
    if there was any failure writing the message.

    Args:
        _type (int): the message type
        error_code (int): the error code of the message, 0 if none

    Attributes:
        _type (int): the message type
        error_code (int): the error code of the message, 0 if none
        data (bytearray): the binary data
    """
    def __init__(self, _type: int, error_code=0):
        self._type = _type
        self.error_code = error_code
        self.data = bytearray()

    def write_event(self, event: Event):
        self.write_uint32(event.time)
        self.write_int32(event.data)

    def write_uint8(self, n):
        self.data.extend(struct.pack('B', n))

    def write_int16(self, n: int):
        self.data.extend(struct.pack('h', n))

    def write_uint16(self, n: int):
        self.data.extend(struct.pack('H', n))

    def write_int32(self, n: int):
        self.data.extend(struct.pack('i', n))

    def write_uint32(self, n: int):
        self.data.extend(struct.pack('I', n))

    def write_double(self, n: float):
        self.data.extend(struct.pack('d', n))

    def write_buffer(self, buffer: bytearray):
        self.data.extend(buffer)

    def write_zeros(self, n_bytes):
        self.data.extend(bytearray(n_bytes))

    def write_int(self, n, size):
        if size == 1:
            self.write_uint8(n)
        elif size == 2:
            if n < 0:
                self.write_int16(n)
            else:
                self.write_uint16(n)
        elif size == 4:
            if n == 0xffffffff:
                self.write_uint32(n)
            else:
                self.write_int32(n)

    def to_data(self) -> bytearray:
        return bytearray(struct.pack('i', self._type)) + bytearray(struct.pack('i', self.error_code)) + self.data

    def __len__(self):
        return 8 + len(self.data)


class ServerException(Exception):
    """
    An exception thrown when the server cannot perform requested operation.
    """
    pass


class TMInterface(object):
    """
    TMInterface is the main class to communicate with the TMInterface server.
    The communication is done through memory mapping and a simple synchronous
    message system between the server and the client. A TMInterface server
    can only serve only one client at a time, it is however possible to connect
    to many servers from the same script.

    The interface provides various functions to manipulate game state
    and hook to different periods of game execution.

    Args:
        server_name (str): the server tag to connect to
        buffer_size (int): the buffer size used by the server, the default is
                           specified by tminterface.constants.DEFAULT_BUFFER_SIZE.
                           Using a custom size requires launching TMInterface with the
                           /serversize command line parameter: TMInterface.exe /serversize=size.

    Attributes:
        server_name (str): the server tag that's used
        running (bool): whether the client is running or not
        registered (bool): whether the client is registered
        mfile (mmap.mmap): the internal mapped file used for communication
        buffer_size (int): the buffer size used for communication
        client (Client): the registered client that's controlling the server
    """
    def __init__(self, server_name='TMInterface0', buffer_size=DEFAULT_SERVER_SIZE):
        self.server_name = server_name
        self.running = True
        self.registered = False
        self.mfile = None
        self.buffer_size = buffer_size
        self.client = None
        self.empty_buffer = bytearray(self.buffer_size)
        self.thread = None
        self.request_close = False

    def register(self, client: Client) -> bool:
        """
        Registers a client on the server. 
        The server can only register one client at a time, if the client is already
        registered, the method will return False.

        This method will initially start a new thread and send a message to the server
        to register a new client. After a successful registration, :meth:`Client.on_registered`
        will be called with the instance of the TMInterface class.

        Args:
            client (Client): a Client instance to register

        Returns:
            True if registration was scheduled, False if client is already registered
        """
        if self.client is not None:
            return False

        if self.registered:
            return False

        self.registered = False
        self.client = client

        if self.thread is None:
            self.thread = threading.Thread(target=self._main_thread)
            self.thread.daemon = True
            self.thread.start()

        return True

    def close(self):
        """
        Closes the connection to the server by deregistering the current client
        and shutting down the thread for communication.

        This method will send a message to the server
        to deregister the current client.

        After a successful deregistration, :meth:`Client.on_deregistered`
        will be called with the instance of the TMInterface class.
        """
        if self.registered:
            msg = Message(MessageType.C_DEREGISTER)
            msg.write_int32(0)
            self._send_message(msg)
            self.client.on_deregistered(self)
            self.thread = None

        self.running = False

    def set_timeout(self, timeout_ms: int):
        """
        Sets the timeout window in which the client has to respond to server calls.

        The timeout specifies how long will the server wait for a response from the client.
        If the response does not arrive in this time frame, the server will automatically deregister the
        client itself.

        The timeout is specified in milliseconds, by default this is 2000ms (2 seconds). Set the timeout
        to -1 to have the server wait forever for the response.

        Args:
            timeout_ms (int): the timeout in milliseconds
        """
        msg = Message(MessageType.C_SET_TIMEOUT)
        msg.write_int32(timeout_ms)
        self._send_message(msg)
        self._wait_for_server_response()

    def set_speed(self, speed: float):
        """
        Sets the global game speed, internally this simply sets the console variable
        "speed" in an TMInterface instance.

        All characteristics of setting the global speed apply. It is not recommended
        to set the speed to high factors (such as >100), which could cause the game
        to skip running some subsystems such as the input subsystem.

        This variable does not affect simulation contexts in which debug mode is disabled.
        When debug mode is disabled (default), the game runs only the simulation subsystem.

        Args:
            speed (float): the speed to set, 1 is the default normal game speed,
                        factors <1 will slow down the game while factors >1 will speed it up
        """
        msg = Message(MessageType.C_SET_GAME_SPEED)
        msg.write_double(speed)
        self._send_message(msg)
        self._wait_for_server_response()

    def set_input_state(self, sim_clear_buffer: bool = True, **kwargs):
        """
        Sets the game input state of the vehicle. 

        Sets individual input states for the car. If successfully applied, 
        key states are guaranteed to be applied at next physics tick.
        If you want to apply an input state that happens at 500ms, call
        send this message at 490ms (one step before). 

        Note that it is not guaranteed that the game will actually process the input
        in the RUN mode. This can happen when setting the game speed to high factors
        (such as >100). This does not affect the simulation context.

        In a simulation context, the server will add new input events to the existing
        event buffer such that that the next tick has the desired input state. By default,
        all other input events are cleared. If you want to preserve existing input state & events,
        pass sim_clear_buffer=False.

        Arguments left, right, accelerate and brake are binary events. 
        To disable an action pass False and to enable it, pass True.

        Arguments steer and gas are analog events. Pass a value in the range of [-65536, 65536] to modify
        the state of these actions. You can also use the extended steer range of [-6553600, 6553600],
        note however that this range is not possible to achieve on physical hardware. This call
        is not affected by the extended_steer console variable.

        Args:
            sim_clear_buffer (bool): whether to clear the event buffer when setting
                                    input state in simulation
            **kwargs: the keyword arguments

        Keyword Args:
            left (bool): the left binary input, False = disabled, True = enabled
            right (bool): the right binary input, False = disabled, True = enabled
            accelerate (bool): the up binary input, False = disabled, True = enabled
            brake (bool): the down binary input, False = disabled, True = enabled
            steer (int): the steer analog input, in range of [-65536, 65536]
            gas (int): the gas analog input, in range of [-65536, 65536]
        """
        if self.get_context_mode() == MODE_SIMULATION and sim_clear_buffer:
            self.clear_event_buffer()

        msg = Message(MessageType.C_SET_INPUT_STATES)
        if 'left' in kwargs:
            msg.write_int32(int(kwargs['left']))
        else:
            msg.write_int32(-1)

        if 'right' in kwargs:
            msg.write_int32(int(kwargs['right']))
        else:
            msg.write_int32(-1)

        if 'accelerate' in kwargs:
            msg.write_int32(int(kwargs['accelerate']))
        else:
            msg.write_int32(-1)

        if 'brake' in kwargs:
            msg.write_int32(int(kwargs['brake']))
        else:
            msg.write_int32(-1)

        if 'steer' in kwargs:
            msg.write_int32(kwargs['steer'])
        else:
            msg.write_int32(MAXINT32)

        if 'gas' in kwargs:
            msg.write_int32(kwargs['gas'])
        else:
            msg.write_int32(MAXINT32)

        self._send_message(msg)
        self._wait_for_server_response()

    def respawn(self, sim_clear_events: bool = True):
        """
        Queues a deterministic respawn at the next race tick. This function
        will not immediately call the game to respawn the car, as TMInterface
        has to call the specific function at a specific place in the game loop.

        In a simulation context, the server will add a new input event to the existing
        event buffer such that that the car respawns at the next tick. By default,
        all other input events are cleared. If you want to preserve existing input events,
        pass sim_clear_events=False.

        The function will respawn the car to the nearest respawnable checkpoint or
        if there was no passed checkpoints, restart the race. The behaviour of this function
        also depends on the start_respawn console variable set within TMInterface.
        If start_respawn is set to true, respawning without any passed checkpoints will
        not restart the race, but only respawn the car on the start block, simulating
        online respawn behaviour.

        Args:
            sim_clear_events (bool): whether to clear all other events in simulation mode
        """
        if self.get_context_mode() == MODE_SIMULATION and sim_clear_events:
            self.clear_event_buffer()

        msg = Message(MessageType.C_RESPAWN)
        msg.write_int32(0)
        self._send_message(msg)
        self._wait_for_server_response()

    def give_up(self):
        """
        Restarts the current race.

        This function does not do anything in a simulation context.
        To rewind to the start of the race in the simulation context, use simulation states.
        """
        msg = Message(MessageType.C_GIVE_UP)
        msg.write_int32(0)
        self._send_message(msg)
        self._wait_for_server_response()

    def horn(self, sim_clear_events: bool = True):
        """
        Queues a deterministic horn at next race tick. This function
        will not immediately call the game to horn, as TMInterface
        has to call the specific function at a specific place in the game loop.

        In a simulation context, the server will add a new input event to the existing
        event buffer such that that the car horns at the next tick. By default,
        all other input events are cleared. If you want to preserve existing input events,
        pass sim_clear_events=False.

        Args:
            sim_clear_events (bool): whether to clear all other events in simulation mode
        """
        if self.get_context_mode() == MODE_SIMULATION and sim_clear_events:
            self.clear_event_buffer()

        msg = Message(MessageType.C_HORN)
        msg.write_int32(0)
        self._send_message(msg)
        self._wait_for_server_response()

    def execute_command(self, command: str):
        """
        Adds an interface command to the internal command queue.

        The command will not be immediately executed, rather, it may be executed when 
        the current queue is processed on the next game frame.

        Args:
            command (str): the command to execute
        """
        msg = Message(MessageType.C_EXECUTE_COMMAND)
        msg.write_int32(0)
        self._write_vector(msg, [ord(c) for c in command], 1)
        self._send_message(msg)
        self._wait_for_server_response()

    def remove_state_validation(self):
        """
        Makes the game validate the replay without checking if the inputs match
        the states saved in the replay, as if it was validating a replay exported
        for validation.

        Calling this method in the on_simulation_begin call will remove state
        validation from currently validated replay. After calling, TrackMania will not
        check if the simulation matches with saved states in the replay,
        therefore allowing for input modification without stopping
        the simulation prematurely.
        """
        msg = Message(MessageType.C_REMOVE_STATE_VALIDATION)
        msg.write_int32(0)
        self._send_message(msg)
        self._wait_for_server_response()

    def prevent_simulation_finish(self):
        """
        Prevents the game from stopping the simulation after a finished race.

        Calling this method in the on_checkpoint_count_changed will invalidate
        checkpoint state so that the game does not stop simulating the race.
        Internally this is simply setting the last checkpoint time to -1
        and can be also done manually in the client if additional handling
        is required.
        """
        msg = Message(MessageType.C_PREVENT_SIMULATION_FINISH)
        msg.write_int32(0)
        self._send_message(msg)
        self._wait_for_server_response()

    def rewind_to_state(self, state: SimStateData):
        """
        Rewinds to the provided simulation state.

        The method of restoring the simulation state slightly varies depending
        on the context_mode field of the SimStateData class. Some buffers
        may not be restored at all but are replaced with native game function calls.

        The simulation state is obtainable through the get_simulation_state method.
        This state can also be used to write a save state compatible file for TMInterface.
        Note that modifying important parts of the state invalidates the current race.

        To provide state restoration across game instances, TMInterface uses
        memory masks to omit restoring instance specific fields such as pointers
        or arrays.

        The method can be called in on_run_step or on_simulation_step calls.
        Note that rewinding to a state in any of these hooks will immediately
        simulate the next step after the hook. For example, rewinding to a state
        saved at race time 0, will result in the next call to on_run_step/on_simulation_step
        being at time 10. If you want to apply any immediate input state,
        make sure to apply it in the same physics step as the call to rewind_to_state.

        Args:
            state (SimStateData): the state to restore, obtained through get_simulation_state
        """
        msg = Message(MessageType.C_SIM_REWIND_TO_STATE)
        msg.write_int32(state.version)
        msg.write_int32(state.context_mode)
        msg.write_int32(state.flags)
        msg.write_buffer(state.timers)
        msg.write_buffer(state.dyna)
        msg.write_buffer(state.scene_mobil)
        msg.write_buffer(state.simulation_wheels)
        msg.write_buffer(state.plug_solid)
        msg.write_buffer(state.cmd_buffer_core)
        msg.write_buffer(state.player_info)
        msg.write_buffer(state.internal_input_state)

        msg.write_event(state.input_running_event)
        msg.write_event(state.input_finish_event)
        msg.write_event(state.input_accelerate_event)
        msg.write_event(state.input_brake_event)
        msg.write_event(state.input_left_event)
        msg.write_event(state.input_right_event)
        msg.write_event(state.input_steer_event)
        msg.write_event(state.input_gas_event)
        msg.write_uint32(state.num_respawns)

        self.__write_checkpoint_state(msg, state.cp_data)
        self._send_message(msg)
        self._wait_for_server_response()

    def set_checkpoint_state(self, data: CheckpointData):
        """
        Sets the checkpoint state of the game.
        See get_checkpoint_state to learn more about how the game stores checkpoint information.

        Args:
            data (CheckpointData): the checkpoint data
        """
        msg = Message(MessageType.C_SET_CHECKPOINT_STATE)
        self.__write_checkpoint_state(msg, data)
        self._send_message(msg)
        self._wait_for_server_response()

    def set_event_buffer(self, data: EventBufferData):
        """
        Replaces the internal event buffer used for simulation with a new one.

        If you do not modify existing inputs or do not generate all events
        beforehand, use TMInterface.set_input_state for dynamic input injection.
        See EventBufferData for more information.

        The events_duration and control_names fields are ignored in this call.

        Args:
            data (EventBufferData): the new event buffer
        """
        msg = Message(MessageType.C_SIM_SET_EVENT_BUFFER)
        for _ in range(10):
            msg.write_int32(-1)

        msg.write_int32(data.events_duration)
        events_tup = [(event.time, event.data) for event in data.events]

        self._write_vector(msg, events_tup, [4, 4])
        self._send_message(msg)
        self._wait_for_server_response()

    def get_context_mode(self) -> int:
        """
        Gets the context mode the TMInterface instance is currently in.

        The context mode is determining if the current race is in
        "run" mode, that is a normal race or "simulation" mode, which is when
        a player validates a replay.

        Returns:
            int: MODE_SIMULATION (0) if the player is in the simulation mode, MODE_RUN (1) if in a normal race
        """
        msg = Message(MessageType.C_GET_CONTEXT_MODE)
        self._send_message(msg)
        self._wait_for_server_response(False)

        self.mfile.seek(8)
        mode = self._read_int32()
        self._clear_buffer()
        return mode

    def get_checkpoint_state(self) -> CheckpointData:
        """
        Gets the current checkpoint state of the race.

        See CheckpointData for more information.

        Returns:
            CheckpointData: the object that holds the two arrays representing checkpoint state
        """
        msg = Message(MessageType.C_GET_CHECKPOINT_STATE)
        self._send_message(msg)
        self._wait_for_server_response(False)

        self.mfile.seek(4)
        error_code = self._read_int32()
        if error_code == NO_PLAYER_INFO:
            raise ServerException('Failed to get checkpoint state: no player info available')

        data = self._read_checkpoint_state()

        self._clear_buffer()
        return data

    def get_simulation_state(self) -> SimStateData:
        """
        Gets the current simulation state of the race.

        The method can be called in on_run_step or on_simulation_step calls.
        See SimStateData for more information.

        Returns:
            SimStateData: the object holding the simulation state
        """
        msg = Message(MessageType.C_SIM_GET_STATE)
        self._send_message(msg)
        self._wait_for_server_response(False)

        self.mfile.seek(4)
        error_code = self._read_int32()

        state = SimStateData()
        state.version = self._read_int32()
        state.context_mode = self._read_int32()
        state.flags = self._read_uint32()
        state.timers = bytearray(self.mfile.read(TIMERS_SIZE))
        state.dyna = bytearray(self.mfile.read(DYNA_SIZE))
        state.scene_mobil = bytearray(self.mfile.read(SCENE_MOBIL_SIZE))
        state.simulation_wheels = bytearray(self.mfile.read(SIMULATION_WHEELS_SIZE))
        state.plug_solid = bytearray(self.mfile.read(PLUG_SOLID_SIZE))
        state.cmd_buffer_core = bytearray(self.mfile.read(CMD_BUFFER_CORE_SIZE))
        state.player_info = bytearray(self.mfile.read(PLAYER_INFO_SIZE))
        state.internal_input_state = bytearray(self.mfile.read(INPUT_STATE_SIZE))

        state.input_running_event = self._read_event()
        state.input_finish_event = self._read_event()
        state.input_accelerate_event = self._read_event()
        state.input_brake_event = self._read_event()
        state.input_left_event = self._read_event()
        state.input_right_event = self._read_event()
        state.input_steer_event = self._read_event()
        state.input_gas_event = self._read_event()
        state.num_respawns = self._read_uint32()

        if error_code == NO_PLAYER_INFO:
            raise ServerException('Failed to get checkpoint state: no player info available')

        state.cp_data = self._read_checkpoint_state()

        self._clear_buffer()
        return state

    def get_event_buffer(self) -> EventBufferData:
        """
        Gets the internal event buffer used to hold player inputs in run or simulation mode.
        If the server is in the run mode (that is, in a normal race controlled by the player),
        this method returns the inputs of the current race. Note that new inputs will be added
        to the buffer as the player or TMInterface injects inputs into the game.

        See EventBufferData for more information.

        Returns:
            EventBufferData: the event buffer holding all the inputs of the current simulation
        """
        msg = Message(MessageType.C_SIM_GET_EVENT_BUFFER)
        self._send_message(msg)
        self._wait_for_server_response(False)

        self.mfile.seek(4)
        error_code = self._read_uint32()
        if error_code == NO_EVENT_BUFFER:
            raise ServerException('Failed to get event buffer: no event buffer available')

        names = [None] * 10
        _id = self._read_int32()
        if _id != -1:
            names[_id] = BINARY_RACE_START_NAME

        _id = self._read_int32()
        if _id != -1:
            names[_id] = BINARY_RACE_FINISH_NAME

        _id = self._read_int32()
        if _id != -1:
            names[_id] = BINARY_ACCELERATE_NAME

        _id = self._read_int32()
        if _id != -1:
            names[_id] = BINARY_BRAKE_NAME

        _id = self._read_int32()
        if _id != -1:
            names[_id] = BINARY_LEFT_NAME

        _id = self._read_int32()
        if _id != -1:
            names[_id] = BINARY_RIGHT_NAME

        _id = self._read_int32()
        if _id != -1:
            names[_id] = ANALOG_STEER_NAME

        _id = self._read_int32()
        if _id != -1:
            names[_id] = ANALOG_ACCELERATE_NAME

        _id = self._read_int32()
        if _id != -1:
            names[_id] = BINARY_RESPAWN_NAME

        _id = self._read_int32()
        if _id != -1:
            names[_id] = BINARY_HORN_NAME

        data = EventBufferData(self._read_uint32())
        data.control_names = names
        event_data = self.__read_vector([4, 4])
        for item in event_data:
            ev = Event(item[0], item[1])
            data.events.append(ev)

        self._clear_buffer()
        return data

    def clear_event_buffer(self):
        """
        Clears the current event buffer used for simulation, leaving
        the race running event in the buffer.

        A race running event should always be present in the buffer, to
        make the game start the race.
        """
        event_buffer = self.get_event_buffer()
        event_buffer.clear()
        self.set_event_buffer(event_buffer)

    def set_simulation_time_limit(self, time: int):
        """
        Sets the time limit of the simulation.

        This allows for setting an arbitrary time limit for the running
        simulation, making the game stop the simulation after the provided
        time limit is exhausted.

        By default, this limit is set to the finish time of the original replay
        (taken from events duration found in the events buffer).

        Note that setting the limit to a large value will extend the simulation
        to that limit, even after the race is finished. Make sure to manage
        finishing the race according to your application (e.g by rewinding to a state).

        To reset the time to the original limit, pass -1.
        This call applies only to the simulation context.

        Args:
            time (int): the time at which the game stops simulating, pass -1 to reset
                        to the original value
        """
        msg = Message(MessageType.C_SIM_SET_TIME_LIMIT)
        msg.write_int32(time)
        self._send_message(msg)
        self._wait_for_server_response()

    def register_custom_command(self, command: str):
        """
        Registers a custom command within the console.

        This function allows you to implement a custom command that is registered within TMInterface's console.
        When executing the command, the :meth:`Client.on_custom_command` method will be called with additional
        arguments such as the time range and processed arguments list.

        It is completely up to the command implementation to process the time range and additional
        arguments supplied in the on_custom_command hook. Quoted arguments such as filenames will
        be automatically joined into one argument, even if they contain spaces. 

        A console command is not immediately executed after submitting it to the console.
        TMInterface executes commands asynchronously, processing a fixed amount of commands
        each frame. This is done to prevent the game from hanging when loading scripts with
        1000's of commands.

        Use the log() method to output any info about the execution of your command.

        Args:
            command (str): the command to register, the command cannot contain spaces
        """
        msg = Message(MessageType.C_REGISTER_CUSTOM_COMMAND)
        msg.write_int32(0)
        self._write_vector(msg, [ord(c) for c in command], 1)
        self._send_message(msg)
        self._wait_for_server_response(False)

        self.mfile.seek(4)
        error_code = self._read_int32()
        if error_code == COMMAND_ALREADY_REGISTERED:
            raise ServerException(f'Failed to register custom command: {command} is already registered')

        self._clear_buffer()

    def log(self, message: str, severity='log'):
        """
        Prints a message in TMInterface's console.

        You can specify the severity of the command to highlight the line in a different color.

        Args:
            message (str): the message to print
            severity (str): one of: "log", "success", "warning", "error", the message severity
        """
        severity_id = 0
        if severity == 'success':
            severity_id = 1
        elif severity == 'warning':
            severity_id = 2
        elif severity == 'error':
            severity_id = 3

        msg = Message(MessageType.C_LOG)
        msg.write_int32(severity_id)
        self._write_vector(msg, [ord(c) for c in message], 1)
        self._send_message(msg)
        self._wait_for_server_response()

    def _on_bruteforce_validate_call(self, msgtype: MessageType):
        info = BFEvaluationInfo()
        info.phase = BFPhase(self._read_int32())
        info.target = BFTarget(self._read_int32())
        info.time = self._read_int32()
        info.modified_inputs_num = self._read_int32()
        info.inputs_min_time = self._read_int32()
        info.inputs_max_time = self._read_int32()
        info.max_steer_diff = self._read_int32()
        info.max_time_diff = self._read_int32()
        info.override_stop_time = self._read_int32()
        info.search_forever = bool(self._read_int32())
        info.inputs_extend_steer = bool(self._read_int32())

        resp = self.client.on_bruteforce_evaluate(self, info)
        if not resp:
            resp = BFEvaluationResponse()

        msg = Message(MessageType.C_PROCESSED_CALL)
        msg.write_int32(msgtype)
        msg.write_int32(resp.decision)
        msg.write_int32(resp.rewind_time)
        self._send_message(msg)

    def __write_checkpoint_state(self, msg: Message, data: CheckpointData):
        msg.write_int32(0)  # reserved
        if self._write_vector(msg, data.cp_states, 4):
            self._write_vector(msg, data.cp_times, [4, 4])

    def _read_checkpoint_state(self):
        self._read_int32()  # reserved
        cp_states = self.__read_vector(4)
        cp_times = self.__read_vector([4, 4])

        data = CheckpointData(cp_states, cp_times)
        return data

    def _read_event(self):
        time = self._read_uint32()
        data = self._read_int32()
        return Event(time, data)

    def _write_vector(self, msg: Message, vector: list, field_sizes):
        is_list = isinstance(field_sizes, list)
        if is_list:
            item_size = sum(field_sizes)
        else:
            item_size = field_sizes

        if len(msg) + 4 > self.buffer_size:
            return False

        vsize = len(vector)
        msgsize = len(msg) + 4 + item_size * vsize
        if msgsize > self.buffer_size:
            msg.write_int32(0)
            msg.error_code = RESPONSE_TOO_LONG
            return True

        msg.write_int32(vsize)
        if is_list:
            for elem in vector:
                for i, field in enumerate(elem):
                    msg.write_int(field, field_sizes[i])
        else:
            for elem in vector:
                msg.write_int(elem, field_sizes)

        return True

    def __read_vector(self, field_sizes: Tuple[int, list]) -> list:
        if self.mfile.tell() + 4 > self.buffer_size:
            return []

        size = self._read_int32()
        vec = []
        for _ in range(size):
            if isinstance(field_sizes, list):
                tup = []
                for size in field_sizes:
                    tup.append(self._read_int(size))

                vec.append(tuple(tup))
            else:
                vec.append(self._read_int(field_sizes))

        return vec

    def _main_thread(self):
        while self.running:
            if not self._ensure_connected():
                time.sleep(0)
                continue

            if not self.registered:
                msg = Message(MessageType.C_REGISTER)
                self._send_message(msg)
                self._wait_for_server_response()
                self.registered = True

            self._process_server_message()
            time.sleep(0)

    def _process_server_message(self):
        if self.mfile is None:
            return

        self.mfile.seek(0)
        msgtype = self._read_int32()
        if msgtype & 0xFF00 == 0:
            return

        msgtype &= 0xFF

        # error_code = self.__read_int32()
        self._skip(4)

        if msgtype == MessageType.S_SHUTDOWN:
            self.close()
            self.client.on_shutdown(self)
        elif msgtype == MessageType.S_ON_RUN_STEP:
            _time = self._read_int32()
            self.client.on_run_step(self, _time)
            self._respond_to_call(msgtype)
        elif msgtype == MessageType.S_ON_SIM_BEGIN:
            self.client.on_simulation_begin(self)
            self._respond_to_call(msgtype)
        elif msgtype == MessageType.S_ON_SIM_STEP:
            _time = self._read_int32()
            self.client.on_simulation_step(self, _time)
            self._respond_to_call(msgtype)
        elif msgtype == MessageType.S_ON_SIM_END:
            result = self._read_int32()
            self.client.on_simulation_end(self, result)
            self._respond_to_call(msgtype)
        elif msgtype == MessageType.S_ON_CHECKPOINT_COUNT_CHANGED:
            current = self._read_int32()
            target = self._read_int32()
            self.client.on_checkpoint_count_changed(self, current, target)
            self._respond_to_call(msgtype)
        elif msgtype == MessageType.S_ON_LAPS_COUNT_CHANGED:
            current = self._read_int32()
            self.client.on_laps_count_changed(self, current)
            self._respond_to_call(msgtype)
        elif msgtype == MessageType.S_ON_BRUTEFORCE_EVALUATE:
            self._on_bruteforce_validate_call(msgtype)
        elif msgtype == MessageType.S_ON_REGISTERED:
            self.registered = True
            self.client.on_registered(self)
            self._respond_to_call(msgtype)
        elif msgtype == MessageType.S_ON_CUSTOM_COMMAND:
            _from = self._read_int32()
            to = self._read_int32()
            n_args = self._read_int32()
            command = self._read_string()
            args = []
            for _ in range(n_args):
                args.append(self._read_string())

            self.client.on_custom_command(self, _from, to, command, args)
            self._respond_to_call(msgtype)

    def _ensure_connected(self):
        if self.mfile is not None:
            return True

        try:
            self.mfile = mmap.mmap(-1, self.buffer_size, tagname=self.server_name)
            return True
        except Exception as e:
            self.client.on_client_exception(self, e)

        return False

    def _wait_for_server_response(self, clear: bool = True):
        if self.mfile is None:
            return

        self.mfile.seek(0)
        while self._read_int32() != MessageType.S_RESPONSE | 0xFF00:
            self.mfile.seek(0)
            time.sleep(0)

        if clear:
            self._clear_buffer()

    def _respond_to_call(self, msgtype: int):
        msg = Message(MessageType.C_PROCESSED_CALL)
        msg.write_int32(msgtype)
        self._send_message(msg)

    def _send_message(self, message: Message):
        if self.mfile is None:
            return

        data = message.to_data()
        self.mfile.seek(0)
        self.mfile.write(data)

        self.mfile.seek(1)
        self.mfile.write(bytearray([0xFF]))

    def _clear_buffer(self):
        self.mfile.seek(0)
        self.mfile.write(self.empty_buffer)

    def _read(self, num_bytes: int, typestr: str):
        arr = self.mfile.read(num_bytes)
        try:
            return struct.unpack(typestr, arr)[0]
        except Exception as e:
            self.client.on_client_exception(self, e)
            return 0

    def _read_int(self, size):
        if size == 1:
            return self._read_uint8()
        if size == 2:
            return self._read_uint16()
        elif size == 4:
            return self._read_int32()

        return 0

    def _read_uint8(self):
        return self._read(1, 'B')

    def _read_int32(self):
        return self._read(4, 'i')

    def _read_uint32(self):
        return self._read(4, 'I')

    def _read_uint16(self):
        return self._read(2, 'H')

    def _read_string(self):
        chars = [chr(b) for b in self.__read_vector(1)]
        return ''.join(chars)

    def _skip(self, n):
        self.mfile.seek(self.mfile.tell() + n)
