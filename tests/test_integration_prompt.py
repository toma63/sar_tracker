import os
import tempfile

import storage
import sar_tracker


class MockAnswer:
    def __init__(self, value):
        self._value = value

    def ask(self):
        return self._value


class MockAsker:
    def __init__(self, answers):
        # answers is an iterator or list we will pop from left
        self._answers = list(answers)

    def _pop(self):
        if not self._answers:
            raise RuntimeError("No more mock answers")
        return self._answers.pop(0)

    def select(self, *args, **kwargs):
        return MockAnswer(self._pop())

    def text(self, *args, **kwargs):
        return MockAnswer(self._pop())


def make_db_path():
    fd, path = tempfile.mkstemp(prefix="itest_sar_", suffix=".db")
    os.close(fd)
    try:
        os.remove(path)
    except OSError:
        pass
    return path


def test_prompting_loop_noninteractive_writes():
    db = make_db_path()
    try:
        writer = storage.open_db_writer(db)
        try:
            # answers sequence:
            # command -> 'status'
            # team -> 'Alpha'
            # location -> 'Grid1'
            # location_status -> 'assigned'
            # transport -> 'self'
            # status_code -> '4 - ok'
            # command -> 'transmission'
            # dest -> 'high bird'
            # src -> 'comms'
            # message -> 'Hello test'
            # command -> 'quit'
            answers = [
                'status', 'Alpha', 'Grid1', 'assigned', 'self', '4 - ok',
                'transmission', 'high bird', 'comms', 'Hello test',
                'quit'
            ]
            asker = MockAsker(answers)
            tactical_calls = ['comms', 'high bird']
            sar_tracker.prompting_loop(tactical_calls, writer, asker=asker)
        finally:
            writer.close()

        data = storage.load_db(db)
        assert data is not None
        assert 'Alpha' in data['status_by_team']
        assert data['location_by_team'].get('Alpha') == 'Grid1'
        assert any(t.get('msg') == 'Hello test' for t in data.get('transmissions', []))
    finally:
        try:
            os.remove(db)
        except OSError:
            pass
