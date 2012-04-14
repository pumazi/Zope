##############################################################################
#
# Copyright (c) 2005 Zope Foundation and Contributors.
#
# This software is subject to the provisions of the Zope Public License,
# Version 2.1 (ZPL).  A copy of the ZPL should accompany this distribution.
# THIS SOFTWARE IS PROVIDED "AS IS" AND ANY AND ALL EXPRESS OR IMPLIED
# WARRANTIES ARE DISCLAIMED, INCLUDING, BUT NOT LIMITED TO, THE IMPLIED
# WARRANTIES OF TITLE, MERCHANTABILITY, AGAINST INFRINGEMENT, AND FITNESS
# FOR A PARTICULAR PURPOSE.
#
##############################################################################
"""App interfaces.
"""

from zope.interface import Attribute
from zope.interface import Interface

# XXX: might contain non-API methods and outdated comments;
#      not synced with ZopeBook API Reference;
#      based on App.Undo.UndoSupport
class IUndoSupport(Interface):

    manage_UndoForm = Attribute("""Manage Undo form""")

    def get_request_var_or_attr(name, default):
        """
        """

    def undoable_transactions(first_transaction=None,
                              last_transaction=None,
                              PrincipiaUndoBatchSize=None):
        """
        """

    def manage_undo_transactions(transaction_info=(), REQUEST=None):
        """
        """
