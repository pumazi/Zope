import os, sys
import unittest
suite = unittest.TestSuite()

def test_suite():
    names = os.listdir(os.path.dirname(__file__))
    tests = [x for x in names \
             if x.startswith('test') and x.endswith('.py') and not x == 'tests.py']

    for test in tests:
        Testing = __import__("Testing.ZopeTestCase.zopedoctest." + test[:-3])
        testmodule = getattr(Testing.ZopeTestCase.zopedoctest, test[:-3])
        if hasattr(testmodule, 'test_suite'):
            suite.addTest(testmodule.test_suite())
    return suite
