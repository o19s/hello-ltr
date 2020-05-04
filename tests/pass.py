import unittest

class Pass(unittest.TestCase):

    def test_that_passes(self):
        assert 1 == 1

if __name__ == "__main__":
    unittest.main()
