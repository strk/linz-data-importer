import sys
import unittest

from test_ldi_plugin import UnitLevel

UiTest
def run_tests():
    suite = unittest.TestSuite()
    suite.addTests(unittest.makeSuite(UnitLevel, "test"))
    unittest.TextTestRunner(verbosity=2, stream=sys.stdout).run(suite)