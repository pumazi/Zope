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
"""Utility functions

These functions are designed to be imported and run at
module level to add functionality to the test environment.

$Id: utils.py 66621 2006-04-06 21:30:58Z slinkp $
"""

import os
import sys
import time
import random
import transaction

def appcall(function, *args, **kw):
    '''Calls a function passing 'app' as first argument.'''
    from base import app, close
    app = app()
    args = (app,) + args
    try:
        return function(*args, **kw)
    finally:
        transaction.abort()
        close(app)
        

def deferToZ2Layer(function):
    '''
    decorator assumes following:

    * function only takes one argument: app
    
    * if app is not passed in, function should be deferred 

    deferral queues execution of the function to the setup call of
    Testing.ZopeTestCase.layer.Zope2Layer
    '''
    def wrapped(*args, **kwargs):
        if args or kwargs.get('app', None):
            return function(*args, **kwargs)
        else:
            import layer
            def curryAppCall(*args, **kwargs):
                return appcall(function, *args, **kwargs)
            return layer._z2_callables.append((curryAppCall, args, kwargs))
    return wrapped


@deferToZ2Layer
def setupCoreSessions(app=None):
    '''Sets up the session_data_manager e.a.'''
    from Acquisition import aq_base
    commit = 0

    if not hasattr(app, 'temp_folder'):
        from Products.TemporaryFolder.TemporaryFolder import MountedTemporaryFolder
        tf = MountedTemporaryFolder('temp_folder', 'Temporary Folder')
        app._setObject('temp_folder', tf)
        commit = 1

    if not hasattr(aq_base(app.temp_folder), 'session_data'):
        from Products.Transience.Transience import TransientObjectContainer
        toc = TransientObjectContainer('session_data',
                    'Session Data Container',
                    timeout_mins=3,
                    limit=100)
        app.temp_folder._setObject('session_data', toc)
        commit = 1

    if not hasattr(app, 'browser_id_manager'):
        from Products.Sessions.BrowserIdManager import BrowserIdManager
        bid = BrowserIdManager('browser_id_manager',
                    'Browser Id Manager')
        app._setObject('browser_id_manager', bid)
        commit = 1

    if not hasattr(app, 'session_data_manager'):
        from Products.Sessions.SessionDataManager import SessionDataManager
        sdm = SessionDataManager('session_data_manager',
                    title='Session Data Manager',
                    path='/temp_folder/session_data',
                    requestName='SESSION')
        app._setObject('session_data_manager', sdm)
        commit = 1

    if commit:
        transaction.commit()

@deferToZ2Layer
def setupZGlobals(app=None):
    '''Sets up the ZGlobals BTree required by ZClasses.'''

    root = app._p_jar.root()
    if not root.has_key('ZGlobals'):
        from BTrees.OOBTree import OOBTree
        root['ZGlobals'] = OOBTree()
        transaction.commit()

@deferToZ2Layer
def setupSiteErrorLog(app=None):
    '''Sets up the error_log object required by ZPublisher.'''

    if not hasattr(app, 'error_log'):
        try:
            from Products.SiteErrorLog.SiteErrorLog import SiteErrorLog
        except ImportError:
            pass
        else:
            app._setObject('error_log', SiteErrorLog())
            transaction.commit()


def importObjectFromFile(container, filename, quiet=0):
    '''Imports an object from a (.zexp) file into the given container.'''
    from ZopeLite import _print, _patched
    quiet = quiet or not _patched
    start = time.time()
    if not quiet: _print("Importing %s ... " % os.path.basename(filename))
    container._importObjectFromFile(filename, verify=0)
    transaction.commit()
    if not quiet: _print('done (%.3fs)\n' % (time.time() - start))


_Z2HOST = None
_Z2PORT = None

def startZServer(number_of_threads=1, log=None):
    '''Starts an HTTP ZServer thread.'''
    global _Z2HOST, _Z2PORT
    if _Z2HOST is None:
        _Z2HOST = '127.0.0.1'
        _Z2PORT = random.choice(range(55000, 55500))
        from ZServer import setNumberOfThreads
        setNumberOfThreads(number_of_threads)
        from threadutils import QuietThread, zserverRunner
        t = QuietThread(target=zserverRunner, args=(_Z2HOST, _Z2PORT, log))
        t.setDaemon(1)
        t.start()
        time.sleep(0.1) # Sandor Palfy
    return _Z2HOST, _Z2PORT


def makerequest(app, stdout=sys.stdout):
    '''Wraps the app into a fresh REQUEST.'''
    from ZPublisher.BaseRequest import RequestContainer
    from ZPublisher.Request import Request
    from ZPublisher.Response import Response
    response = Response(stdout=stdout)
    environ = {}
    environ['SERVER_NAME'] = _Z2HOST or 'nohost'
    environ['SERVER_PORT'] = '%d' % (_Z2PORT or 80)
    environ['REQUEST_METHOD'] = 'GET'
    request = Request(sys.stdin, environ, response)
    request._steps = ['noobject'] # Fake a published object
    request['ACTUAL_URL'] = request.get('URL') # Zope 2.7.4

    # set Zope3-style default skin so that the request is usable for
    # Zope3-style view look-ups
    from zope.app.publication.browser import setDefaultSkin
    setDefaultSkin(request)

    return app.__of__(RequestContainer(REQUEST=request))





def makelist(arg):
    '''Turns arg into a list. Where arg may be
       list, tuple, or string.
    '''
    if type(arg) == type([]):
        return arg
    if type(arg) == type(()):
        return list(arg)
    if type(arg) == type(''):
       return filter(None, [arg])
    raise ValueError('Argument must be list, tuple, or string')

def hasProduct(name):
    '''Checks if a product can be found along Products.__path__'''
    from OFS.Application import get_products
    return name in [n[1] for n in get_products()]

def _print(msg):
    '''Writes 'msg' to stderr and flushes the stream.'''
    sys.stderr.write(msg)
    sys.stderr.flush()

def setDebugMode(mode):
    '''
    Allows manual setting of Five's inspection of debug mode to allow for
    zcml to fail meaningfully
    '''
    import Products.Five.fiveconfigure as fc
    fc.debug_mode=mode

def setAllLayers(suite, newlayer):
    '''
    helper function that iterates through all the subsuites in a
    suite, resetting their layer to @param layer: the desired layer
    class
    '''
    [setattr(subsuite, 'layer', newlayer) for subsuite in suite]
    return suite

__all__ = [
    'setupCoreSessions',
    'setupSiteErrorLog',
    'setupZGlobals',
    'startZServer',
    'importObjectFromFile',
    'appcall',
    'makerequest',
    'makelist',
    'hasProduct',
    'setDebugMode',
    '_print',
    'setAllLayers'
]

