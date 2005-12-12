##############################################################################
#
# Copyright (c) 2005 Zope Corporation and Contributors. All Rights Reserved.
#
# This software is subject to the provisions of the Zope Public License,
# Version 2.1 (ZPL).  A copy of the ZPL should accompany this distribution.
# THIS SOFTWARE IS PROVIDED "AS IS" AND ANY AND ALL EXPRESS OR IMPLIED
# WARRANTIES ARE DISCLAIMED, INCLUDING, BUT NOT LIMITED TO, THE IMPLIED
# WARRANTIES OF TITLE, MERCHANTABILITY, AGAINST INFRINGEMENT, AND FITNESS
# FOR A PARTICULAR PURPOSE
#
##############################################################################
__version__='$Revision$'[11:-2]

import transaction
from zope.event import notify
from zope.interface import implements
from zope.publisher.interfaces import IRequest, IPublication
from zope.publisher.interfaces import NotFound, IPublicationRequest
from zope.app.publication.interfaces import EndRequestEvent
from zope.app.publication.interfaces import BeforeTraverseEvent

from ZPublisher.Publish import Retry
from ZPublisher.Publish import get_module_info, call_object
from ZPublisher.Publish import missing_name, dont_publish_class
from ZPublisher.mapply import mapply
from ZPublisher.BaseRequest import RequestContainer

class ZopePublication(object):
    """Base Zope2 publication specification.
    """
    implements(IPublication)

    def __init__(self, db=None, module_name="Zope2"):
        # db is a ZODB.DB.DB object.
        # XXX We don't use this yet.
        self.db = db

        # Published module, bobo-style.
        self.module_name = module_name

        # Fetch module info to be backwards compatible with 'bobo'
        # and Zope 2.
        (self.bobo_before, self.bobo_after,
         self.application, self.realm, self.debug_mode,
         self.err_hook, self.validated_hook,
         self.transactions_manager) = get_module_info(self.module_name)

    def beforeTraversal(self, request):
        # First part of old ZPublisher.Publish.publish. Call
        # 'bobo_before' hooks and start a new transaction using the
        # 'transaction_manager'.
        if self.bobo_before is not None:
            self.bobo_before()
        if self.transactions_manager:
            self.transactions_manager.begin()

    def callTraversalHooks(self, request, ob):
        # Call __before_publishing_traverse__ hooks the Zope 3-way by
        # firing an event.
        notify(BeforeTraverseEvent(ob, request))

    def afterTraversal(self, request, ob):
        # XXX Authentication should happen here. It used to happen at
        # the end of BaseRequest.traverse().

        # Zope 2 does annotate the transaction just after traversal,
        # but before calling the object. Zope 3 does annotate the
        # transaction on afterCall instead.
        txn = transaction.get()
        self.annotateTransaction(txn, request, ob)

    def getApplication(self, request):
        # Return the application object for the given module.
        ob = self.application

        # Now, some code from ZPublisher.BaseRequest:
        # If the top object has a __bobo_traverse__ method, then use it
        # to possibly traverse to an alternate top-level object.
        if hasattr(ob, '__bobo_traverse__'):
            try:
                ob = ob.__bobo_traverse__(request)
            except:
                # XXX Blind except? Yuck!
                pass

        if hasattr(ob, '__of__'):
            # Try to bind the top-level object to the request
            # This is how you get 'self.REQUEST'
            ob = ob.__of__(RequestContainer(REQUEST=request))

        return ob

    def callObject(self, request, ob):
        # Call the object the same way it's done in Zope 2.

        # XXX Check if it's a Zope 3 or a Zope 2 request. Might not be
        # true because someone (Five?) is saying that the Zope 2
        # request implements IPublicationRequest so we check for the
        # method name. Yuck.
        if (IPublicationRequest.providedBy(request) and
            hasattr(request, 'getPositionalArguments')):
            args = request.getPositionalArguments()
        else:
            # It's a Zope 2 request.
            args = request.args
        return mapply(ob, args,
                      request, call_object, 1, missing_name,
                      dont_publish_class, request, bind=1)

    def afterCall(self, request, ob):
        # Last part of ZPublisher.Publish.{publish, publish_module_standard},
        # commit the transaction.
        if self.transactions_manager:
            self.transactions_manager.commit()

    def endRequest(self, request, ob):
        # End the request the Zope 3-way, by firing an event.
        notify(EndRequestEvent(ob, request))

    def annotateTransaction(self, txn, request, ob):
        """Set some useful meta-information on the transaction. This
        information is used by the undo framework, for example.

        This method is not part of the `IPublication` interface, since
        it's specific to this particular implementation.
        """
        # Zope 2 uses the 'recordMetadata' method of the transaction
        # manager to record the transaction metadata.
        if self.transactions_manager:
            self.transactions_manager.recordMetaData(ob, request)

    def _abort(self):
        if self.transactions_manager:
            self.transactions_manager.abort()

    def handleException(self, object, request, exc_info, retry_allowed=True):
        # Some exception handling from ZPublisher.Publish.publish().
        if self.err_hook is None:
            self._abort()
            raise

        # If an err_hook was registered, use it.
        try:
            try:
                return self.err_hook(object, request,
                                     exc_info[0],
                                     exc_info[1],
                                     exc_info[2],
                                     )
            except Retry:
                if not retry_allowed:
                    return self.err_hook(object, request,
                                         exc_info[0],
                                         exc_info[1],
                                         exc_info[2],
                                         )
        finally:
            self._abort()

        # XXX After this code, in ZPublisher.Publish.publish(), Zope 2
        # does a 'Retry' if a 'Retry' exception happens and the
        # request supports retry. It's not clear how this will be
        # handled by Zope 3.

    def traverseName(self, request, ob, name, acquire=True):
        if hasattr(ob, '__bobo_traverse__'):
            try:
                subob = ob.__bobo_traverse__(request, name)
                if type(subob) is type(()) and len(subob) > 1:
                    # XXX Yuck! __bobo_traverse__ might return more
                    # than one object!
                    #
                    # Add additional parents into the path
                    #
                    # parents[-1:] = list(subob[:-1])
                    # ob, subob = subob[-2:]
                    raise NotImplementedError
                else:
                    return subob
            except (AttributeError, KeyError):
                raise NotFound(ob, name)

        # Should only get this far if the object doesn't have a
        # __bobo_traverse__ method.
        try:
            # Note - no_acquire_flag is necessary to support
            # things like DAV.  We have to make sure
            # that the target object is not acquired
            # if the request_method is other than GET
            # or POST. Otherwise, you could never use
            # PUT to add a new object named 'test' if
            # an object 'test' existed above it in the
            # heirarchy -- you'd always get the
            # existing object :(
            if (acquire and hasattr(ob, 'aq_base')):
                if hasattr(ob.aq_base, name):
                    return getattr(ob, name)
                else:
                    raise AttributeError, name
            else:
                return getattr(ob, name)
        except AttributeError:
            got = 1
            try:
                return ob[name]
            except (KeyError, IndexError,
                    TypeError, AttributeError):
                raise NotFound(ob, name)

_publication = None
def get_publication(module_name=None):
    global _publication
    if module_name is None:
        module_name = "Zope2"
    if _publication is None:
        _publication = ZopePublication(db=None, module_name=module_name)
    return _publication
