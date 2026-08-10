import io
import unittest
from contextlib import redirect_stdout

from app.main import main


class MainTests(unittest.TestCase):
    def test_main_prints_startup_message(self):
        output = io.StringIO()

        with redirect_stdout(output):
            main()

        self.assertEqual(output.getvalue().strip(), "Hello from backend!")


if __name__ == "__main__":
    unittest.main()
