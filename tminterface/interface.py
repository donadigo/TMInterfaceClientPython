import struct
import threading
import time
import mmap
from .client import Client
from .structs import Event, CheckpointData, SimStateData, EventBufferData
from .sizes import *
from enum import IntEnum, auto

class MessageType(IntEnum):
    S_RESPONSE = auto()
    S_SHUTDOWN = auto()
    S_ON_RUN_STEP = auto()
    S_ON_SIM_BEGIN = auto()
    S_ON_SIM_STEP = auto()
    S_ON_SIM_END = auto()
    S_ON_CHECKPOINT_COUNT_CHANGED = auto()
    S_ON_LAPS_COUNT_CHANGED = auto()
    C_REGISTER = auto()
    C_DEREGISTER = auto()
    C_PROCESSED_CALL = auto()
    C_SET_INPUT_STATES = auto()
    C_RESPAWN = auto()
    C_SIM_REWIND_TO_STATE = auto()
    C_SIM_GET_STATE = auto()
    C_SIM_GET_EVENT_BUFFER = auto()
    C_GET_CONTEXT_MODE = auto()
    C_SIM_SET_EVENT_BUFFER = auto()
    C_GET_CHECKPOINT_STATE = auto()
    C_SET_CHECKPOINT_STATE = auto()
    C_SET_GAME_SPEED = auto()
    C_EXECUTE_COMMAND = auto()
    C_SET_EXECUTE_COMMANDS = auto()
    C_SET_TIMEOUT = auto()
    C_REMOVE_STATE_VALIDATION = auto()
    C_PREVENT_SIMULATION_FINISH = auto()
    ANY = auto()

RESPONSE_TOO_LONG = 1
CLIENT_ALREADY_REGISTERED = 2
NO_EVENT_BUFFER = 3
NO_PLAYER_INFO = 4

MAXINT32 = 2 ** 31 - 1

class Message(object):
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
        if size  == 1:
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


class TMInterface(object):
    ''' 
    TMInterface is the main class to communicate with the TMInterface server.
    The communication is done through memory mapping and a simple synchronous
    message system between the server and the client. A TMInterface server
    can only serve only one client at a time, it is however possible to connect
    to many servers from the same script.

    The interface provides various functions to manipulate game state
    and hook to different periods of game execution. 

    Args:
        server_name (str): the server tag to connect to
        buffer_size (int): the buffer size used by the server, by default it's 16834

    Attributes:
        server_name (str): the server tag that's used
        running (bool): whether the client is running or not
        registered (bool): whether the client is registered
        mfile (mmap.mmap): the internal mapped file used for communication
        buffer_size (int): the buffer size used for communication
        client (Client): the registered client that's controlling the server
    '''
    def __init__(self, server_name='TMInterface0'):
        self.server_name = server_name
        self.running = True
        self.registered = False
        self.mfile = None
        self.buffer_size = 65536
        self.client = None
        self.empty_buffer = bytearray(self.buffer_size)
        self.thread = None

    '''
    Registers a client on the server. 
    The server can only register one client at a time, if the client is already
    registered, the method will return False.

    This method will initially start a new thread and send a message to the server
    to register a new client. After a successful registration, Client.on_registered
    will be called with the instance of the TMInterface class.

    Args:
        client (Client): a Client instance to register
    
    Returns:
        True if registration was scheduled, False if client is already registered
    '''
    def register(self, client: Client) -> bool:
        if self.client is not None:
            return False

        if self.registered:
            return False

        self.registered = False
        self.client = client

        if self.thread is None:
            self.thread = threading.Thread(target=self.__main_thread)
            self.thread.daemon = True
            self.thread.start()

        return True

    '''
    Closes the connection to the server by deregistering the current client
    and shutting down the thread for communication.

    This method will send a message to the server
    to deregister the current client.

    After a successful deregistration, Client.on_deregistered
    will be called with the instance of the TMInterface class.
    '''
    def close(self):
        self.running = False

        if self.registered:
            msg = Message(MessageType.C_DEREGISTER)
            self.__send_message(msg)
            self.__wait_for_server_response()
            self.client.on_deregistered(self)

            if self.thread is not None:
                self.thread = None

    '''
    Sets the timeout window in which the client has to respond to server calls.

    The timeout specifies how long will the server wait for a response from the client.
    If the response does not arrive in this time frame, the server will automatically deregister the
    client itself.

    The timeout is specified in milliseconds, by default this is 2000ms (2 seconds). Set the timeout
    to -1 to have the server wait forever for the response.

    Args:
        timeout_ms (int): the timeout in milliseconds
    '''
    def set_timeout(self, timeout_ms: int):
        msg = Message(MessageType.C_SET_TIMEOUT)
        msg.write_int32(timeout_ms)
        self.__send_message(msg)
        self.__wait_for_server_response()

    '''
    Sets the global game speed, internally this simply sets the console variable
    "speed" in an TMInterface instance.

    All characteristics of setting the global speed apply. It is not recommended
    to set the speed to high factors (such as >100), which could cause the game
    to skip running some subsystems such as the input subsystem.

    Args:
        speed (float): the speed to set, 1 is the default normal game speed,
                       factors <1 will slow down the game while factors >1 will speed it up
    '''
    def set_speed(self, speed: float):
        msg = Message(MessageType.C_SET_GAME_SPEED)
        msg.write_double(speed)
        self.__send_message(msg)
        self.__wait_for_server_response()

    '''
    Sets the game input state of the vehicle. 

    Sets individual input states for the car. If successfully applied, 
    key states are guaranteed to be applied at next step of the run.
    If you want to apply an input state that happens at 500ms, call
    send this message at 490ms (one step before). 

    Note that it is not guaranteed that the game will actually process the input. This
    can happen when setting the game speed to high factors (such as >100). 

    This function does not work in simulation context. To set input state in that context,
    use event buffers (get_event_buffer).

    Arguments left, right, up and down are by default set to -1 which signifies that the input
    should not modified for these actions. To disable an action pass 0 and to enable it, pass 1.

    Arguments steer and gas are by default set to MAXINT32 which signifies that the input
    should not modified for these actions. Pass a value in the range of [-65536, 65536] to modify
    the state of these actions. You can also use the extended steer range of [-6553600, 6553600],
    note however that this range is not possible to achieve on physical hardware. This call
    is not affected by the extended_steer console variable.

    Args:
        left (int): the left binary input, -1 by default, 0 = disabled, 1 = enabled
        right (int): the right binary input, -1 by default, 0 = disabled, 1 = enabled
        up (int): the up binary input, -1 by default, 0 = disabled, 1 = enabled
        down (int): the down binary input, -1 by default, 0 = disabled, 1 = enabled
        steer (int): the steer analog input, MAXINT32 by default
        gas (int): the gas analog input, MAXINT32 by default
    '''
    def set_input_state(self, left=-1, right=-1, up=-1, down=-1, steer=MAXINT32, gas=MAXINT32):
        msg = Message(MessageType.C_SET_INPUT_STATES)
        msg.write_int32(left)
        msg.write_int32(right)
        msg.write_int32(up)
        msg.write_int32(down)
        msg.write_int32(steer)
        msg.write_int32(gas)
        self.__send_message(msg)
        self.__wait_for_server_response()

    '''
    Adds an interface command to the internal command queue.

    The command will not be immediately executed, rather, it may be executed when 
    the current queue is processed on the next game frame.

    Args:
        command (str): the command to execute
    '''
    def execute_command(self, command: str):
        msg = Message(MessageType.C_EXECUTE_COMMAND)
        msg.write_int32(0)
        self.__write_vector(msg, [ord(c) for c in command], 1)
        self.__send_message(msg)
        self.__wait_for_server_response()

    '''
    Makes the game validate the replay without checking if the inputs match
    the states saved in the replay, as if it was validating a replay exported
    for validation.

    Calling this method in the on_simulation_begin call will remove state
    validation from currently validated replay. After calling, TrackMania will not
    check if the simulation matches with saved states in the replay,
    therefore allowing for input modification without stopping
    the simulation prematurely.
    '''
    def remove_state_validation(self):
        msg = Message(MessageType.C_REMOVE_STATE_VALIDATION)
        msg.write_int32(0)
        self.__send_message(msg)
        self.__wait_for_server_response()

    '''
    Prevents the game from stopping the simulation after a finished race.

    Calling this method in the on_checkpoint_count_changed will invalidate
    checkpoint state so that the game does not stop simulating the race.
    Internally this is simply setting the last checkpoint time to -1
    and can be also done manually in the client if additional handling
    is required.
    '''
    def prevent_simulation_finish(self):
        msg = Message(MessageType.C_PREVENT_SIMULATION_FINISH)
        msg.write_int32(0)
        self.__send_message(msg)
        self.__wait_for_server_response()

    '''
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

    Args:
        state (SimStateData): the state to restore, obtained through get_simulation_state
    '''
    def rewind_to_state(self, state: SimStateData):
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

        msg.write_event(state.input_running_state)
        msg.write_event(state.input_finish_state)
        msg.write_event(state.input_accelerate_state)
        msg.write_event(state.input_brake_state)
        msg.write_event(state.input_left_state)
        msg.write_event(state.input_right_state)
        msg.write_event(state.input_steer_state)
        msg.write_event(state.input_gas_state)
        msg.write_uint32(state.num_respawns)

        self.__write_checkpoint_state(msg, state.cp_data)
        self.__send_message(msg)
        self.__wait_for_server_response()

    '''
    Sets the checkpoint state of the game.
    See get_checkpoint_state to learn more about how the game stores checkpoint information.

    Args:
        data (CheckpointData): the checkpoint data
    '''
    def set_checkpoint_state(self, data: CheckpointData):
        msg = Message(MessageType.C_SET_CHECKPOINT_STATE)
        self.__write_checkpoint_state(msg, data)
        self.__send_message(msg)
        self.__wait_for_server_response()

    '''
    Replaces the internal event buffer used for simulation with a new one.


    Args:
        data (EventBufferData): the new event buffer
    '''
    def set_event_buffer(self, data: EventBufferData):
        msg = Message(MessageType.C_SIM_SET_EVENT_BUFFER)
        for _ in range(9):
            msg.write_int32(-1)
            
        msg.write_int32(data.events_duration)
        events_tup = [(event.time, event.data) for event in data.events]

        self.__write_vector(msg, events_tup, [4, 4])
        self.__send_message(msg)
        self.__wait_for_server_response()

    '''
    Gets the context mode the TMInterface instance is currently in.

    The context mode is determining if the current race is in
    "run" mode, that is a normal race or "simulation" mode, which is when
    a player validates a replay.

    Returns:
        int: 0 if the player is in the simulation mode, 1 if in a normal race
    '''
    def get_context_mode(self) -> int:
        msg = Message(MessageType.C_GET_CONTEXT_MODE)
        self.__send_message(msg)
        self.__wait_for_server_response(False)

        self.mfile.seek(8)
        self.__clear_buffer()
        return self.__read_int32()

    '''
    Gets the current checkpoint state of the race.

    The game keeps track of two arrays that contain checkpoint information.

    The first "state" array is an array of booleans (a boolean is 4 bytes long)
    and keeps track of which checkpoints were already passed. The length of the 
    array represents the real count of the checkpoints on current the map (including finish).
    This does not mean that to finish the race the player has to pass through this exact count
    of checkpoints. A map with 3 laps and 5 checkpoints will still contain only 5 checkpoint states.

    The second "times" array is an array of structures with 2 fields: time and an unknown field.
    This array holds the "logical" number of checkpoints that have to be passed (including finish).
    This means the total number of checkpoint passes, including the existence of laps.

    Returns:
        CheckpointData that holds the two arrays representing checkpoint state
    '''
    def get_checkpoint_state(self) -> CheckpointData:
        msg = Message(MessageType.C_GET_CHECKPOINT_STATE)
        self.__send_message(msg)
        self.__wait_for_server_response(False)

        self.mfile.seek(4)
        error_code = self.__read_int32()
        if (error_code & NO_PLAYER_INFO) == 0:
            data = self.__read_checkpoint_state()
        else:
            data = None

        self.__clear_buffer()
        return data

    '''
    Gets the current simulation state of the race.

    The simulation state consists of raw memory buffers representing various
    information about the race state. This includes the entirety of the vehicle
    state as well as the player info and other state variables such as current
    checkpoint count and input state.

    The method can be called in on_run_step or on_simulation_step calls.

    Returns:
        SimStateData holding the simulation state
    '''
    def get_simulation_state(self) -> SimStateData:
        msg = Message(MessageType.C_SIM_GET_STATE)
        self.__send_message(msg)
        self.__wait_for_server_response(False)

        self.mfile.seek(4)
        error_code = self.__read_int32()

        state = SimStateData()
        state.version = self.__read_int32()
        state.context_mode = self.__read_int32()
        state.flags = self.__read_uint32()
        state.timers = bytearray(self.mfile.read(TIMERS_SIZE))
        state.dyna = bytearray(self.mfile.read(DYNA_SIZE))
        state.scene_mobil = bytearray(self.mfile.read(SCENE_MOBIL_SIZE))
        state.simulation_wheels = bytearray(self.mfile.read(SIMULATION_WHEELS_SIZE))
        state.plug_solid = bytearray(self.mfile.read(PLUG_SOLID_SIZE))
        state.cmd_buffer_core = bytearray(self.mfile.read(CMD_BUFFER_CORE_SIZE))
        state.player_info = bytearray(self.mfile.read(PLAYER_INFO_SIZE))
        state.internal_input_state = bytearray(self.mfile.read(INPUT_STATE_SIZE))

        state.input_running_state = self.__read_event()
        state.input_finish_state  = self.__read_event()
        state.input_accelerate_state = self.__read_event()
        state.input_brake_state  = self.__read_event()
        state.input_left_state  = self.__read_event()
        state.input_right_state = self.__read_event()
        state.input_steer_state = self.__read_event()
        state.input_gas_state = self.__read_event()
        state.num_respawns = self.__read_uint32()

        if (error_code & NO_PLAYER_INFO) == 0:
            state.cp_data = self.__read_checkpoint_state()
        else:
            state.cp_data = CheckpointData(0, 0, [], [])

        self.__clear_buffer()
        return state

    '''
    Gets the internal event buffer used to hold player inputs in simulation mode.

    While simulating a race, the game loads the inputs from a replay file
    into an internal buffer and begins to apply "events" (inputs) from this
    buffer. The buffer itself consists of 8 byte values, the first 4 bytes
    is used for the event time and the last 4 is used for event data.

    The event time is so called a "stored" time. The stored time is
    defined as 100000 + race time. The stored time is saved in the
    replay file and is also used in the internal buffer itself.

    The event data is a 4 byte value consisting of the control name
    index (the event type such as Accelerate, Brake etc.) and the
    actual value used to describe the event. See EventBufferData 
    for more information.

    The buffer itself is stored in *decreasing* order. That means that the event
    at index 0 in the list is the last one simulated in the race. The start and end
    of the race is marked by special "_FakeIsRaceRunning" and "_FakeFinishLine" events.
    These events mark the start and finish of the race, note that without the presence
    of "_FakeIsRaceRunning" event, the race will not start at all. This event has a
    constant stored time of 100000. 
    
    Before the starting event, a "Respawn" event can be generated by the game, this
    event can also be saved in the replay file itself. The very first input that can be applied
    by the player happens at stored time of 100010. 

    Returns:
        EventBufferData holding all the inputs of the current simulation
    '''
    def get_event_buffer(self) -> EventBufferData:
        msg = Message(MessageType.C_SIM_GET_EVENT_BUFFER)
        self.__send_message(msg)
        self.__wait_for_server_response(False)

        self.mfile.seek(4)
        error_code = self.__read_uint32()
        if error_code == NO_EVENT_BUFFER:
            return EventBufferData(0)

        names = {}
        _id = self.__read_int32()
        if _id != -1:
            names[_id] = '_FakeIsRaceRunning'
        
        _id = self.__read_int32()
        if _id != -1:
            names[_id] = '_FakeFinishLine'

        _id = self.__read_int32()
        if _id != -1:
            names[_id] = 'Accelerate'
            
        _id = self.__read_int32()
        if _id != -1:
            names[_id] = 'Brake'

        _id = self.__read_int32()
        if _id != -1:
            names[_id] = 'SteerLeft'

        _id = self.__read_int32()
        if _id != -1:
            names[_id] = 'SteerRight'

        _id = self.__read_int32()
        if _id != -1:
            names[_id] = 'Steer'
            
        _id = self.__read_int32()
        if _id != -1:
            names[_id] = 'Gas'

        _id = self.__read_int32()
        if _id != -1:
            names[_id] = 'Respawn'

        data = EventBufferData(self.__read_uint32())
        data.control_names = names
        event_data = self.__read_vector([4, 4])
        for item in event_data:
            ev = Event(item[0], item[1])
            data.events.append(ev)
            
        self.__clear_buffer()
        return data

    def __write_checkpoint_state(self, msg: Message, data: CheckpointData):
        msg.write_int32(0) # reserved
        if self.__write_vector(msg, data.cp_states, 4):
            self.__write_vector(msg, data.cp_times, [4, 4])

    def __read_checkpoint_state(self):
        self.__read_int32() # reserved
        cp_states = self.__read_vector(4)
        cp_times = self.__read_vector([4, 4])

        data = CheckpointData(cp_states, cp_times)
        return data

    def __read_event(self):
        time = self.__read_uint32()
        data = self.__read_int32()
        return Event(time, data)

    def __write_vector(self, msg: Message, vector: list, field_sizes):
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

    def __read_vector(self, field_sizes) -> list:
        if self.mfile.tell() + 4 > self.buffer_size:
            return []

        size = self.__read_int32()
        vec = []
        for _ in range(size):
            if isinstance(field_sizes, list):
                tup = []
                for size in field_sizes:
                    tup.append(self.__read_int(size))

                vec.append(tuple(tup))
            else:
                vec.append(self.__read_int(field_sizes))
        
        return vec

    def __main_thread(self):
        while self.running:
            if not self.__ensure_connected():
                time.sleep(0)
                continue

            if not self.registered:
                msg = Message(MessageType.C_REGISTER)
                self.__send_message(msg)
                self.__wait_for_server_response()
                self.client.on_registered(self)
                self.registered = True

            self.__process_server_message()
            time.sleep(0)

    def __process_server_message(self):
        if self.mfile is None:
            return
        
        self.mfile.seek(0)
        msgtype = self.__read_int32()
        if msgtype & 0xFF00 == 0:
            return

        msgtype &= 0xFF

        # error_code = self.__read_int32()
        self.__skip(4)

        if msgtype == MessageType.S_SHUTDOWN:
            self.client.on_shutdown(self)
            self.__respond_to_call(msgtype)
            self.registered = False
            self.close()
        elif msgtype == MessageType.S_ON_RUN_STEP:
            time = self.__read_int32()
            self.client.on_run_step(self, time)
            self.__respond_to_call(msgtype)
        elif msgtype == MessageType.S_ON_SIM_BEGIN:
            self.client.on_simulation_begin(self)
            self.__respond_to_call(msgtype)
        elif msgtype == MessageType.S_ON_SIM_STEP:
            time = self.__read_int32()
            self.client.on_simulation_step(self, time)
            self.__respond_to_call(msgtype)
        elif msgtype == MessageType.S_ON_SIM_END:
            result = self.__read_int32()
            self.client.on_simulation_end(self, result)
            self.__respond_to_call(msgtype)   
        elif msgtype == MessageType.S_ON_CHECKPOINT_COUNT_CHANGED:
            current  = self.__read_int32()
            target = self.__read_int32()
            self.client.on_checkpoint_count_changed(self, current, target)
            self.__respond_to_call(msgtype)
        elif msgtype == MessageType.S_ON_LAPS_COUNT_CHANGED:
            current = self.__read_int32()
            self.client.on_laps_count_changed(self, current)
            self.__respond_to_call(msgtype)

    def __ensure_connected(self):
        if self.mfile is not None:
            return True
            
        try:
            self.mfile = mmap.mmap(-1, self.buffer_size, tagname=self.server_name)
            return True
        except Exception as e:
            print(e)

        return False

    def __wait_for_server_response(self, clear=True):
        if self.mfile is None:
            return

        self.mfile.seek(0)
        while self.__read_int32() != MessageType.S_RESPONSE | 0xFF00:
            self.mfile.seek(0)
            time.sleep(0)

        # self.mfile.seek(4)
        # error_code = self.__read_int32()
        # if error_code != 0:
        #     print('Got error code:', error_code)
        
        # self.mfile.seek(0)

        if clear:
            self.__clear_buffer()

    def __respond_to_call(self, msgtype: int):
        msg = Message(MessageType.C_PROCESSED_CALL)
        msg.write_int32(msgtype)
        self.__send_message(msg)

    def __send_message(self, message: Message):
        if self.mfile is None:
            return
        
        data = message.to_data()
        self.mfile.seek(0)
        self.mfile.write(data)

        self.mfile.seek(1)
        self.mfile.write(bytearray([0xFF]))

    def __clear_buffer(self):
        self.mfile.seek(0)
        self.mfile.write(self.empty_buffer)

    def __read(self, num_bytes: int, typestr: str):
        try:
            return struct.unpack(typestr, self.mfile.read(num_bytes))[0]
        except Exception as e:
            print(e)
            return 0

    def __read_int(self, size):
        if size == 1:
            return self.__read_uint8()
        if size == 2:
            return self.__read_uint16()
        elif size == 4:
            return self.__read_int32()
        
        return 0

    def __read_uint8(self):
        return self.__read(1, 'B')

    def __read_int32(self):
        return self.__read(4, 'i')
    
    def __read_uint32(self):
        return self.__read(4, 'I')

    def __read_uint16(self):
        return self.__read(2, 'H')

    def __skip(self, n):
        self.mfile.seek(self.mfile.tell() + n)
