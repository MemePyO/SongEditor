from undo_stack import UndoStack


class TestUndoStack:
    def test_initial_state(self):
        stack = UndoStack("a")
        assert stack.current() == "a"
        assert not stack.can_undo()
        assert not stack.can_redo()

    def test_push_and_undo(self):
        stack = UndoStack("a")
        stack.push("b")
        stack.push("c")
        assert stack.current() == "c"
        assert stack.can_undo()
        assert stack.undo() == "b"
        assert stack.undo() == "a"
        assert stack.undo() is None
        assert not stack.can_undo()

    def test_redo(self):
        stack = UndoStack("a")
        stack.push("b")
        assert stack.undo() == "a"
        assert stack.can_redo()
        assert stack.redo() == "b"
        assert stack.redo() is None
        assert not stack.can_redo()

    def test_push_same_state_is_noop(self):
        stack = UndoStack("a")
        stack.push("a")
        assert not stack.can_undo()
        stack.push("b")
        stack.push("b")
        assert stack.undo() == "a"

    def test_redo_branch_discarded_on_new_push(self):
        stack = UndoStack("a")
        stack.push("b")
        stack.undo()
        stack.push("c")
        assert not stack.can_redo()
        assert stack.undo() == "a"

    def test_max_size_trims_oldest(self):
        stack = UndoStack("", max_size=3)
        for i in range(5):
            stack.push(str(i))
        assert stack.current() == "4"
        # Oldest states were trimmed: "0" and "1" are gone.
        assert stack.undo() == "3"
        assert stack.undo() == "2"
        assert stack.undo() is None

    def test_reset(self):
        stack = UndoStack("a")
        stack.push("b")
        stack.reset("z")
        assert stack.current() == "z"
        assert not stack.can_undo()
        assert not stack.can_redo()
