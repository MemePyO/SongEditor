"""Generic undo/redo stack for widget values (e.g. Entry text)."""


class UndoStack:
    """A simple state-based undo/redo stack.

    ``push`` records a new state; ``undo``/``redo`` walk back and forth through
    the recorded states. States are compared for equality, so redundant pushes
    are ignored and pushing a new state discards any redo branch.
    """

    def __init__(self, initial="", max_size=100):
        self._states = [initial]
        self._index = 0
        self._max_size = max_size

    def push(self, state):
        if state == self._states[self._index]:
            return
        # A new state invalidates any redo branch.
        del self._states[self._index + 1:]
        self._states.append(state)
        if len(self._states) > self._max_size:
            del self._states[0]
        self._index = len(self._states) - 1

    def undo(self):
        if not self.can_undo():
            return None
        self._index -= 1
        return self._states[self._index]

    def redo(self):
        if not self.can_redo():
            return None
        self._index += 1
        return self._states[self._index]

    def can_undo(self):
        return self._index > 0

    def can_redo(self):
        return self._index < len(self._states) - 1

    def current(self):
        return self._states[self._index]

    def reset(self, state=""):
        self._states = [state]
        self._index = 0
