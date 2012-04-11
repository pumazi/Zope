##############################################################################
#
# Copyright (c) 2006 Zope Foundation and Contributors.
# All Rights Reserved.
#
# This software is subject to the provisions of the Zope Public License,
# Version 2.1 (ZPL).  A copy of the ZPL should accompany this distribution.
# THIS SOFTWARE IS PROVIDED "AS IS" AND ANY AND ALL EXPRESS OR IMPLIED
# WARRANTIES ARE DISCLAIMED, INCLUDING, BUT NOT LIMITED TO, THE IMPLIED
# WARRANTIES OF TITLE, MERCHANTABILITY, AGAINST INFRINGEMENT, AND FITNESS
# FOR A PARTICULAR PURPOSE.
#
##############################################################################
"""Components manager(s)
"""

from Products.Five.component import enableSite, disableSite
from Products.Five.component.interfaces import (
    IObjectManagerSite, IObjectManagerSiteManager,
    )

from zope.interface import implements
from zope.component.globalregistry import base
from zope.component.persistentregistry import PersistentComponents
from zope.site.hooks import setSite


class ObjectManagerSiteManager(object):
    implements(IObjectManagerSiteManager)

    def __init__(self, context):
        self.context = context

    @property
    def is_site(self):
        return IObjectManagerSite.providedBy(self.context)

    def make_site(self):
        if IObjectManagerSite.providedBy(self.context):
            raise ValueError('This is already a site')

        enableSite(self.context, iface=IObjectManagerSite)

        #TODO in the future we'll have to walk up to other site
        # managers and put them in the bases
        components = PersistentComponents()
        components.__bases__ = (base,)
        self.context.setSiteManager(components)

    def unmake_site(self):
        if not self.is_site:
            raise ValueError('This is not a site')

        disableSite(self.context)

        # disableLocalSiteHook circumcised our context so that it's
        # not an ISite anymore.  That can mean that certain things for
        # it can't be found anymore.  So, for the rest of this request
        # (which will be over in about 20 CPU cycles), already clear
        # the local site from the thread local.
        setSite()

        self.context.setSiteManager(None)
