##############################################################################
#
# Copyright (c) 2005 Zope Corporation and Contributors. All Rights Reserved.
#
# This software is subject to the provisions of the Zope Public License,
# Version 2.1 (ZPL).  A copy of the ZPL should accompany this distribution.
# THIS SOFTWARE IS PROVIDED "AS IS" AND ANY AND ALL EXPRESS OR IMPLIED
# WARRANTIES ARE DISCLAIMED, INCLUDING, BUT NOT LIMITED TO, THE IMPLIED
# WARRANTIES OF TITLE, MERCHANTABILITY, AGAINST INFRINGEMENT, AND FITNESS
# FOR A PARTICULAR PURPOSE.
#
##############################################################################
"""
layer support for ZopeTestCase

$Id: $
"""
import os
from utils import setDebugMode

class ZopeLiteLayer:
    @classmethod
    def setUp(cls):
        import ZopeLite

    @classmethod
    def tearDown(cls):
        raise NotImplementedError

# products to install
_products=[]

# setup functions
_z2_callables=[]
class Zope2Layer(ZopeLiteLayer):
    """ stacks upon ZopeLiteLayer and handles products installs """
    @classmethod
    def setUp(cls):
        import ZopeLite as Zope2
        install = Zope2.installProduct
        
        [install(name, quiet=quiet) \
         for name, quiet in _products]

        [func(*args, **kw) for func, args, kw in _z2_callables]
        import transaction as txn
        txn.commit()

    @classmethod
    def tearDown(cls):
        raise NotImplementedError


def installProduct(name, quiet=0):
    if not (name, quiet) in _products:
        _products.append((name, quiet))
