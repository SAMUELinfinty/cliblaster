import unittest
from cliblaster.music_queue import Queue
from cliblaster.track import Track

class TestQueue(unittest.TestCase):
    def setUp(self):
        self.queue = Queue()
        self.t1 = Track("Song1", "Unknown", "s1.mp3")
        self.t2 = Track("Song2", "Unknown", "s2.mp3")
        self.t3 = Track("Song3", "Unknown", "s3.mp3")

    def test_initial_state(self):
        self.assertEqual(len(self.queue.all()), 0)
        self.assertIsNone(self.queue.current())
        self.assertIsNone(self.queue.next())
        self.assertIsNone(self.queue.previous())

    def test_add_tracks(self):
        self.queue.add(self.t1)
        self.assertEqual(self.queue.current(), self.t1)
        self.assertEqual(self.queue.current_index, 0)
        
        self.queue.add(self.t2)
        self.assertEqual(self.queue.current(), self.t1) # current should not change
        self.assertEqual(len(self.queue.all()), 2)

    def test_next_previous(self):
        self.queue.add(self.t1)
        self.queue.add(self.t2)
        self.queue.add(self.t3)

        self.assertEqual(self.queue.current(), self.t1)
        
        self.assertEqual(self.queue.next(), self.t2)
        self.assertEqual(self.queue.current_index, 1)

        self.assertEqual(self.queue.next(), self.t3)
        self.assertEqual(self.queue.current_index, 2)

        # Boundary: already at the end
        self.assertEqual(self.queue.next(), self.t3)
        self.assertEqual(self.queue.current_index, 2)

        self.assertEqual(self.queue.previous(), self.t2)
        self.assertEqual(self.queue.current_index, 1)

        self.assertEqual(self.queue.previous(), self.t1)
        self.assertEqual(self.queue.current_index, 0)

        # Boundary: already at the beginning
        self.assertEqual(self.queue.previous(), self.t1)
        self.assertEqual(self.queue.current_index, 0)

    def test_remove(self):
        self.queue.add(self.t1)
        self.queue.add(self.t2)
        self.queue.add(self.t3)

        self.queue.next() # current is t2 (index 1)
        
        # Remove previous item (index 0)
        self.assertTrue(self.queue.remove(0))
        self.assertEqual(len(self.queue.all()), 2)
        self.assertEqual(self.queue.current(), self.t2)
        self.assertEqual(self.queue.current_index, 0) # shifted!

        # Remove current item
        self.assertTrue(self.queue.remove(0))
        self.assertEqual(self.queue.current(), self.t3)
        self.assertEqual(self.queue.current_index, 0)

        # Remove invalid
        self.assertFalse(self.queue.remove(99))

        # Remove last item
        self.queue.remove(0)
        self.assertIsNone(self.queue.current())
        self.assertEqual(self.queue.current_index, -1)

    def test_clear(self):
        self.queue.add(self.t1)
        self.queue.add(self.t2)
        self.queue.clear()
        self.assertEqual(len(self.queue.all()), 0)
        self.assertIsNone(self.queue.current())

    def test_duplicate_tracks(self):
        self.queue.add(self.t1)
        self.queue.add(self.t1)
        self.assertEqual(len(self.queue.all()), 2)
        self.assertEqual(self.queue.next(), self.t1)
        self.assertEqual(self.queue.current_index, 1)

if __name__ == "__main__":
    unittest.main()
