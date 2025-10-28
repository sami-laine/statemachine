import unittest
import threading

from statemachine import StateMachine, State


class TestStateMachine(unittest.TestCase):
    def setUp(self):
        class TestMachine(StateMachine):
            def __init__(self):
                super().__init__()
                self.a = State("A")
                self.b = State("B")
                self.c = State("C")
                self.d = State("D")

                self.a_to_b = self.connect(self.a, self.b)
                self.b_to_c = self.connect(self.b, self.c)
                self.connect(self.c, self.d, automatic=True)

                self.initial_state = self.a

            def on_state_changed(self, from_state, to_state):
                self.last_transition = (from_state, to_state)

        self.sm = TestMachine()
        self.sm.start()

    def test_basic_transition(self):
        self.sm.a_to_b()
        self.assertEqual(self.sm.state, self.sm.b)

    def test_use_context_manager(self):
        with self.sm.use():
            self.sm.a_to_b()
            self.sm.b_to_c()
        self.assertEqual(self.sm.state, self.sm.c)

    def test_when_context_manager(self):
        # Move to state C so automatic transition to D can happen
        self.sm.a_to_b()
        self.sm.b_to_c()

        def wait_and_check():
            with self.sm.when(self.sm.d):
                self.assertEqual(self.sm.state, self.sm.d)

        thread = threading.Thread(target=wait_and_check)
        thread.start()
        thread.join(timeout=2)

    def test_thread_safety_with_use(self):
        results = []

        def thread_job():
            with self.sm.use():
                self.sm.a_to_b()
                results.append(self.sm.state.name)

        thread = threading.Thread(target=thread_job)
        thread.start()
        thread.join()

        self.assertIn("B", results)

    def test_state_change_callback(self):
        self.sm.a_to_b()
        self.assertEqual(self.sm.last_transition, (self.sm.a, self.sm.b))


if __name__ == "__main__":
    unittest.main()
