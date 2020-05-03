import unittest

class Fail(unittest.TestCase):

    def test_that_fails(self):
        assert 1 == 0

if __name__ == "__main__":
    unittest.main()
