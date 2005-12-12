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

    module_name = "Zope2"

    def __init__(self, db):
        # db is a ZODB.DB.DB object.
        # XXX We don't use this yet.
        self.db = db

        # Fetch module info the to be backwards compatible with 'bobo'
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
        return mapply(ob, request.getPositionalArguments(),
                      request, call_object, 1, missing_name,
                      dont_publish_class, request, bind=1)

    def afterCall(self, request, ob):
        # Last part of ZPublisher.Publish.{publish, publish_module_standard},
        # commit the transaction and call 'bobo_after' hook if one was
        # provided.
        if self.transactions_manager:
            self.transactions_manager.commit()
        if self.bobo_after is not None:
            self.bobo_after()

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

    def handleException(self, object, request, exc_info, retry_allowed=True):
        # Some exception handling from ZPublisher.Publish.publish().
        if self.err_hook is None:
            if transactions_manager:
                transactions_manager.abort()
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
            if self.transactions_manager:
                self.transactions_manager.abort()

        # XXX After this code, in ZPublisher.Publish.publish(), Zope 2
        # does a 'Retry' if a 'Retry' exception happens and the
        # request supports retry. It's not clear how this will be
        # handled by Zope 3.
