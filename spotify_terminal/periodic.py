import time

from . import common


logger = common.logging.getLogger(__name__)


class PeriodicCallback(object):
    """Execute a callback at certain intervals."""

    def __init__(self, period, func, args=(), kwargs={}, active=True):
        self.period = period
        """How often to run."""

        self.func = func
        """The function to call."""

        self.args = args
        """Arguments for the function."""

        self.kwargs = kwargs
        """Keyward arguments for the fucntion."""

        self.active = active
        """Whether active or not."""

        self._next_call_time = time.time()
        """The next time to call the function."""

    def update(self, call_time):
        if call_time >= self._next_call_time and self.active:
            self.func(*self.args, **self.kwargs)
            self._next_call_time += self.period

    def call_at(self, call_time):
        self._next_call_time = call_time

    def call_in(self, delta):
        self._next_call_time = time.time() + delta

    def call_now(self):
        self.call_in(0)

    def is_active(self):
        return self.active

    def activate(self):
        logger.debug("%s: Activating", self)
        self.active = True
        self.call_now()

    def deactivate(self):
        logger.debug("%s: Deactivating", self)
        self.active = False

    def __str__(self):
        return "{}({}, {})".format(self.func.__name__, self.args, self.kwargs)


class PeriodicDispatcher(object):
    """Dispatches a set of PeriodicCallbacks"""

    def __init__(self, periodics):
        self.periodics = periodics
        """The PeriodicCallbacks to dispatch."""

    def dispatch(self):
        """Dispatch all PeriodicCallbacks."""
        for p in self.periodics:
            p.update(time.time())