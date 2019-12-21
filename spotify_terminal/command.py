from . import common


logger = common.logging.getLogger(__name__)


class CommandProcessor(object):
    """Processed input and determines what commands to fun."""

    def __init__(self, trigger, commands):
        """Constructor.

        Args:
            trigger (str): The default trigger for all commands.
            commands (dict): Map of str commands to callables to execute.
        """
        self.default_trigger = trigger
        """The default trigger. All command will start with this trigger."""

        self.custom_triggers = {}
        """Custom triggers that can bind to custom commands."""

        self.commands = commands
        """Dictionary of commands to functions."""

        self.shorthand_commands = {}
        """Map of shorthand commands to full commands."""

        self.command_history = ["exit"]
        """History of commands that have been executed."""

        self.command_history_i = 0
        """History of commands."""

        self.prev_command_toks = ["exit"]
        """The tokens of the previous command that was executed."""

    def bind_trigger(self, trigger, command_prefix):
        """Bind a trigger to a custom command.

        <trigger> <args> turns into <command_prefix> <args>.

        Args:
            trigger (str, collection): The trigger(s) to bind.
            command_prefix (str): The command prefix to bind to.
        """
        if isinstance(trigger, str):
            trigger = [trigger]

        for t in trigger:
            self.custom_triggers[t] = command_prefix

    def bind(self, shorthand, command):
        """Bind a shorthand command to a command.

        Args:
            shorthand (str, list): The short hand char or chars.
            command (str): The command to bind to.
        """
        assert command in self.commands
        
        if isinstance(shorthand, str):
            shorthand = [shorthand]

        for sh in shorthand:
            self.shorthand_commands[sh] = command

    def process_command(self, command_input, save=False):
        logger.debug("Pre-processing command: %s", command_input)

        # Convert everything to string first
        if not isinstance(command_input, str):
            command_input = str(command_input)

        if not command_input:
            return

        # If no trigger, assume the default and prepend it.
        trigger = command_input[0]
        if trigger != self.default_trigger and trigger not in self.custom_triggers:
            command_input = "{}{}".format(self.default_trigger, command_input)

        if trigger in self.custom_triggers:
            command_prefix = self.custom_triggers[trigger]
            command_input = "{}{} {}".format(self.default_trigger, command_prefix, command_input[1::])

        if command_input[1::] in self.shorthand_commands:
            command_input = "{}{}".format(self.default_trigger, self.shorthand_commands[command_input[1::]])

        logger.debug("Processing command: %s", command_input)

        # Get tokens after removing the trigger
        assert command_input[0] == self.default_trigger
        toks = command_input[1::].split()

        # Get the command.
        command = toks[0]

        # Execute the command if it exists.
        if command not in self.commands:
            logger.debug("%s is not a valid command", command)
        else:
            logger.debug("Final command: %s", toks)
            # Get the arguments for the command.
            command_args = toks[1::] if len(toks) > 1 else []

            # Save as the last command.
            self.prev_command_toks = toks

            # Execute the appropriate command.
            try:
                self.commands[command](*command_args)
            except Exception as e:
                if common.DEBUG:
                    raise
                else:
                    logger.warning("Invalid command: %s", e)

        if save:
            self.command_history.append(command_input)
            self.command_history_i = len(self.command_history)

    def back(self):
        if self.command_history_i > 0:
            self.command_history_i -= 1
        else:
            self.command_history_i = 0

    def forward(self):
        if self.command_history_i < (len(self.command_history) - 1):
            self.command_history_i += 1
        else:
            self.command_history_i = len(self.command_history) - 1

    def get_command(self):
        return self.command_history[self.command_history_i]

    def get_prev_cmd_toks(self):
        return self.prev_command_toks

    def get_triggers(self):
        return [self.default_trigger] + list(self.custom_triggers.keys())


class TextQuery(object):
    def __init__(self, init_text=""):
        self.text_cursor_i = 0
        """The cursor location of the command."""

        self.text_query = []
        """The command being typed."""

        for char in init_text:
            self.insert(char)

    def delete(self):
        if self.text_cursor_i > 0:
            self.text_query.pop(self.text_cursor_i - 1)
            self.text_cursor_i -= 1

    def clear(self):
        while self.text_cursor_i > 0:
            self.delete()

    def insert(self, char):
        self.text_query.insert(self.text_cursor_i, char)
        self.text_cursor_i += 1

    def cursor_left(self):
        if self.text_cursor_i > 0:
            self.text_cursor_i -= 1

    def cursor_right(self):
        if self.text_cursor_i < len(self.text_query):
            self.text_cursor_i += 1

    def get_cursor_index(self):
        return self.text_cursor_i

    def get_current_index(self):
        if self.text_query and (self.text_cursor_i < len(self.text_query)):
            return self.text_query[self.text_cursor_i]
        else:
            return ""

    def empty(self):
        return len(self.text_query) == 0

    def __str__(self):
        return "".join(self.text_query)
