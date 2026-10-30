import unittest

from screen_capture.annotations import History, Line, Step, Style

S = Style((1, 0, 0, 1), 3)


class HistoryTest(unittest.TestCase):
    def test_history_undo_redo_roundtrip(self):
        h = History()
        a, b = Line((0, 0), (1, 1), S), Line((2, 2), (3, 3), S)
        h.add(a)
        h.add(b)
        h.undo()
        self.assertEqual(h.shapes, [a])
        h.redo()
        self.assertEqual(h.shapes, [a, b])

    def test_add_after_undo_clears_redo(self):
        h = History()
        h.add(Line((0, 0), (1, 1), S))
        h.undo()
        h.add(Line((5, 5), (6, 6), S))
        h.redo()
        self.assertEqual(len(h.shapes), 1)
        self.assertEqual(h.shapes[0].p0, (5, 5))

    def test_undo_redo_on_empty_is_noop(self):
        h = History()
        h.undo()
        h.redo()
        self.assertEqual(h.shapes, [])

    def test_next_step_number_follows_visible_steps(self):
        h = History()
        self.assertEqual(h.next_step_number(), 1)
        h.add(Step((10, 10), h.next_step_number(), S))
        h.add(Step((20, 20), h.next_step_number(), S))
        self.assertEqual(h.next_step_number(), 3)
        h.undo()
        self.assertEqual(h.next_step_number(), 2)


class HistoryFlagsTest(unittest.TestCase):
    def test_can_undo_and_can_redo_flags(self):
        h = History()
        self.assertFalse(h.can_undo)
        self.assertFalse(h.can_redo)
        h.add(Line((0, 0), (1, 1), S))
        self.assertTrue(h.can_undo)
        h.undo()
        self.assertFalse(h.can_undo)
        self.assertTrue(h.can_redo)
