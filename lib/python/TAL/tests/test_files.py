#! /usr/bin/env python1.5
"""Tests that run driver.py over input files comparing to output files."""

import os
import sys
import glob

import utils
import unittest

from TAL import runtest

class FileTestCase(unittest.TestCase):

    def __init__(self, file, dir):
        self.__file = file
        self.__dir = dir
        unittest.TestCase.__init__(self)

    def runTest(self):
        sys.stdout.write(os.path.basename(self.__file) + " ")
        sys.stdout.flush()
        sys.argv = ["", "-Q", self.__file]
        pwd = os.getcwd()
        try:
            try:
                os.chdir(self.__dir)
                runtest.main()
            finally:
                os.chdir(pwd)
        except SystemExit, what:
            if what.code:
                self.fail("output for %s didn't match" % self.__file)

try:
    script = __file__
except NameError:
    script = sys.argv[0]

def test_suite():
    suite = unittest.TestSuite()
    dir = os.path.dirname(script)
    dir = os.path.abspath(dir)
    parentdir = os.path.dirname(dir)
    prefix = os.path.join(dir, "input", "test*.")
    xmlargs = glob.glob(prefix + "xml")
    xmlargs.sort()
    htmlargs = glob.glob(prefix + "html")
    htmlargs.sort()
    args = xmlargs + htmlargs
    if not args:
        sys.stderr.write("Warning: no test input files found!!!\n")
    for arg in args:
        case = FileTestCase(arg, parentdir)
        suite.addTest(case)
    return suite

if __name__ == "__main__":
    errs = utils.run_suite(test_suite())
    sys.exit(errs and 1 or 0)
