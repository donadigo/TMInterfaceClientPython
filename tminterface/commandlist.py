from dataclasses import dataclass
from enum import IntEnum
from io import IOBase

BOT_COMMANDS = ['press', 'rel', 'steer', 'gas']
BOT_INPUT_TYPES = ['up', 'down', 'left', 'right', 'enter', 'delete', 'horn', 'steer', 'gas']


class InputType(IntEnum):
    """
    The InputType enum represents an input type that is coupled with its state.
    """
    UP = 0
    DOWN = 1
    LEFT = 2
    RIGHT = 3
    RESPAWN = 4
    RESET = 5
    HORN = 6
    STEER = 7
    GAS = 8
    UNKNOWN = 9

    @staticmethod
    def from_str(s: str):
        """
        Converts a script action string into an InputType.

        If the action is invalid, InputType.UNKNOWN will be returned.

        Args:
            s (str): the string to convert

        Returns:
            InputType: the converted input type
        """
        s = s.lower()
        if s not in BOT_INPUT_TYPES:
            return InputType.UNKNOWN

        return InputType(BOT_INPUT_TYPES.index(s))

    def to_str(self) -> str:
        if int(self) < len(BOT_INPUT_TYPES):
            return BOT_INPUT_TYPES[int(self)]
        else:
            return 'unknown'


class BaseCommand:
    """
    The BaseCommand class is a base class for all command classes such as Command, TimedCommand and InputCommand.
    """
    def to_script(self) -> str:
        """
        Converts a command to a script string line.

        Returns:
            str: the script snippet that represents this command
        """
        pass


@dataclass
class Command(BaseCommand):
    """
    A Command represents an immediate command that is executed immediately by TMInterface whenever it's encountered.
    """
    args: list

    def to_script(self) -> str:
        return ' '.join(self.args)


@dataclass
class InputCommand(BaseCommand):
    """
    The InputCommand class specifically represents a command that is used to inject any kind of input into the game.

    An input does not contain any arguments. Instead, the class defines an input with its type and state.
    InputCommand's can be converted from an instance of TimedCommand.

    InputCommand's do not need to be stored to describe a TMInterface script, they are however automatically added
    by the CommandList for an easy access & manipulation of the input sequence.
    """
    timestamp: int
    input_type: InputType
    state: int

    def to_script(self) -> str:
        if self.input_type == InputType.STEER or self.input_type == InputType.GAS:
            return f'{self.timestamp} {self.input_type.to_str()} {self.state}'
        elif self.input_type == InputType.UNKNOWN:
            return f'# {self.timestamp} [unknown] {int(self.state)}'
        else:
            action = 'press' if self.state else 'rel'
            return f'{self.timestamp} {action} {self.input_type.to_str()}'


@dataclass
class TimedCommand(Command):
    """
    A TimedCommand describes any command that is executed at a specific timestamp.

    The TimedCommand can represent any command, including any input commands.
    A command with a ranged timestamp will be always converted to two TimedCommand instances,
    where the earliest command will have is_ending set to False and the latest, to True.
    """
    timestamp: int
    is_ending: bool

    def to_input_command(self) -> InputCommand:
        """
        Converts a TimedCommand to an InputCommand if possible.

        If the conversion fails or the TimedCommand is not a valid input command, None is returned.

        Returns:
            InputCommand: the converted InputCommand, or None if the conversion failed
        """
        if len(self.args) < 2 or self.args[0].lower() not in BOT_COMMANDS:
            return None

        state = 0
        action = self.args[0].lower()
        input_type = InputType.UNKNOWN
        if action == 'press' or action == 'rel':
            if action == 'press' and not self.is_ending:
                state = 1

            input_type = InputType.from_str(self.args[1])
        elif action == 'steer' or action == 'gas':
            input_type = InputType.from_str(action)

            if not self.is_ending:
                try:
                    state = int(self.args[1])
                except ValueError:
                    return None
        else:
            return None

        return InputCommand(self.timestamp, input_type, state)

    def to_script(self) -> str:
        input_command = self.to_input_command()
        if input_command:
            return input_command.to_script()

        return f'{self.timestamp} {super().to_script()}'


class CommandList(object):
    """
    A CommandList represents a list of TMInterface commands usually forming a script which can contain immediate
    and timed commands.

    A CommandList can be loaded by providing a file handle to an existing script file or from a string.
    You can also construct an empty CommandList to add your own commands to then convert them 
    into a valid TMInterface script.

    If a resource is provided, the class will attempt to parse all of its contents into immediate and timed commands.
    You can use CommandList.to_script() to convert all the commands back into a valid TMInterface script.
    If any command cannot be converted, it will be commented out.

    The class fully supports parsing commands with quoted arguments and inline comments and can be used
    to genereate new script files.

    Args:
        obj: the resource that needs to be parsed, either:

             a file handle opened with open()

             a string containing the command list

             None to create an empty list

    Attributes:
        commands (list): the list containing all immediate commands
        timed_commands (list): the list containing all timed commands, including input commands
        content (str): the script string that was used to construct the CommandList
    """
    def __init__(self, obj=None):
        self.commands = []
        self.timed_commands = []
        self.content = None

        if obj:
            if isinstance(obj, IOBase):
                self.content = obj.read()
            else:
                self.content = obj

            self._parse()

    def _parse(self):
        for line in self.content.split('\n'):
            line = line.split('#')[0].strip()
            if not line or line.startswith('#'):
                continue

            for command in CommandList._split_input(line):
                self._parse_command(command)

    def _parse_command(self, command):
        args = CommandList._split_command_args(command)
        if not args:
            return

        _from, _to = CommandList.parse_time_range(args[0])
        if _from != -1:
            self.add_command(TimedCommand(args[1:], _from, False))

            if _to != -1:
                self.add_command(TimedCommand(args[1:], _to, True))
        else:
            self.commands.append(Command(args))

    def sorted_timed_commands(self) -> list:
        """
        Returns all timed commands sorted in ascending order (stable).

        Returns:
            list: timed commands sorted in ascending order
        """
        return sorted(self.timed_commands, key=lambda command: command.timestamp)

    def add_command(self, command: BaseCommand):
        """
        Adds a command to the CommandList, converting it to an InputCommand if possible.

        The command will be added to the commands list if it is of type Command.
        If the command is a TimedCommand, it will first be attempted to convert it
        to an InputCommand. If the conversion fails, it is added without any conversions.
        If the command is an InputCommnad, it is added to the timed_commands list.

        Args:
            command (BaseCommand): the command to be added
        """
        if type(command) == Command:
            self.commands.append(command)
        elif type(command) == TimedCommand:
            input_command = command.to_input_command()
            if input_command:
                self.timed_commands.append(input_command)
            else:
                self.timed_commands.append(command)
        elif type(command) == InputCommand:
            self.timed_commands.append(command)

    def to_script(self) -> str:
        """
        Converts all immediate and timed commands to a valid TMInterface script.

        Returns:
            str: the string representing the TMInterface script, one command per line
        """
        script = ''
        for command in self.commands:
            script += f'{command.to_script()}\n'

        for command in self.sorted_timed_commands():
            script += f'{command.to_script()}\n'

        return script

    def clear(self):
        """
        Clears all commands from the command list.
        """
        self.commands.clear()
        self.timed_commands.clear()

    @staticmethod
    def _split_input(command_input: str) -> list:
        in_quotes = False
        commands = []
        offset = 0
        for i, c in enumerate(command_input):
            if c == '\"':
                in_quotes = not in_quotes

            if not in_quotes and c == ';':
                commands.append(command_input[offset:i])
                offset = i + 1

        if len(command_input) - offset > 0:
            commands.append(command_input[offset:])

        return commands

    @staticmethod
    def _split_command_args(command: str) -> list:
        args = []
        offset = 0
        i = 0
        while i < len(command):
            if command[i] == ' ':
                if command[offset] != ' ':
                    args.append(command[offset:i])

                offset = i + 1
            elif command[i] == '\"':
                i += 1
                closing = command.find('\"', i)
                if closing != -1:
                    if closing - i > 0:
                        args.append(command[i:closing])

                    i = closing
                    offset = i + 1

            i += 1

        if len(command) - offset > 0:
            args.append(command[offset:])

        return args

    @staticmethod
    def parse_time_range(range_str: str) -> tuple:
        """
        Parses a time range.

        Parses a time range or a single timestamp, returning a tuple
        with two elements (from, to).

        If the parsed time range consists only of one timestamp, to is set to -1.
        If from > to, the two integers are swapped.

        Args:
            range_str (str): the time range to parse

        Returns:
            tuple: a tuple of two int's (from, to)
        """
        timestamps = range_str.split('-', 1)
        timestamps_len = len(timestamps)
        if timestamps_len == 1:
            return CommandList.parse_time(timestamps[0]), -1
        elif timestamps_len == 2:
            _from = CommandList.parse_time(timestamps[0])
            _to = CommandList.parse_time(timestamps[1])
            if _from > _to:
                _from, _to = _to, _from

            return _from, _to

        return -1, -1

    @staticmethod
    def _parse_seconds(time_str: str) -> int:
        tokens = time_str.split('.', 1)
        if len(tokens) < 2:
            return -1

        if not tokens[0] or not tokens[1]:
            return -1

        tokens[1] = tokens[1][:2].ljust(2, '0')

        try:
            seconds = int(tokens[0])
            milliseconds = int(tokens[1])
            return seconds * 1000 + milliseconds * 10
        except ValueError:
            return -1

    @staticmethod
    def parse_time(time_str: str) -> int:
        """
        Parses a singular timestamp which is either a number or a formatted time.

        Parses a string like "947120" or "15:47.12" to an integer time in milliseconds.

        Args:
            time_str (str): the time string to parse

        Returns:
            int: the time representing the string, -1 if parsing fails
        """
        if '.' not in time_str:
            try:
                return int(time_str)
            except ValueError:
                return -1

        tokens = time_str.split(':', 2)
        if not tokens:
            return -1

        tokens_len = len(tokens)
        if tokens_len == 1:
            return CommandList._parse_seconds(time_str)
        elif tokens_len == 2:
            try:
                minutes = int(tokens[0])
            except ValueError:
                return -1

            seconds = CommandList._parse_seconds(tokens[1])
            if seconds == -1:
                return -1

            return minutes * 60000 + seconds
        elif tokens_len == 3:
            try:
                hours = int(tokens[0])
                minutes = int(tokens[1])
            except ValueError:
                return - 1

            seconds = CommandList._parse_seconds(tokens[2])
            if seconds == -1:
                return -1

            return hours * 3600000 + minutes * 60000 + seconds

        return -1
