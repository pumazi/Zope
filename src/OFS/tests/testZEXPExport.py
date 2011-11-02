##############################################################################
#
# Copyright (c) 2011 Zope Foundation and Contributors.
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

from persistent.mapping import PersistentMapping

import transaction
import ZODB
import ZODB.FileStorage
import ZODB.tests.util


class ZEXPExportTests(ZODB.tests.util.TestCase):

    def setUp(self):
        ZODB.tests.util.TestCase.setUp(self)
        self._storage = ZODB.FileStorage.FileStorage(
            'ZODBTests.fs', create=1)
        self._db = ZODB.DB(self._storage)

    def tearDown(self):
        self._db.close()
        ZODB.tests.util.TestCase.tearDown(self)

    def populate(self):
        transaction.begin()
        conn = self._db.open()
        root = conn.root()
        root['test'] = pm = PersistentMapping()
        for n in range(100):
            pm[n] = PersistentMapping({0: 100 - n})
        transaction.get().note('created test data')
        transaction.commit()
        conn.close()

    def testExportImport(self, abort_it=False):
        self.populate()
        conn = self._db.open()
        try:
            self.duplicate(conn, abort_it)
        finally:
            conn.close()
        conn = self._db.open()
        try:
            self.verify(conn, abort_it)
        finally:
            conn.close()

    def duplicate(self, conn, abort_it):
        from OFS.ZEXPExport import exportZEXP
        
        transaction.begin()
        transaction.get().note('duplication')
        root = conn.root()
        ob = root['test']
        assert len(ob) > 10, 'Insufficient test data'
        try:
            import tempfile
            f = tempfile.TemporaryFile()
            exportZEXP(ob, f)
            assert f.tell() > 0, 'Did not export correctly'
            f.seek(0)
            new_ob = ob._p_jar.importFile(f)
            self.assertEqual(new_ob, ob)
            root['dup'] = new_ob
            f.close()
            if abort_it:
                transaction.abort()
            else:
                transaction.commit()
        except:
            transaction.abort()
            raise

    def verify(self, conn, abort_it):
        transaction.begin()
        root = conn.root()
        ob = root['test']
        try:
            ob2 = root['dup']
        except KeyError:
            if abort_it:
                # Passed the test.
                return
            else:
                raise
        else:
            self.failUnless(not abort_it, 'Did not abort duplication')
        l1 = list(ob.items())
        l1.sort()
        l2 = list(ob2.items())
        l2.sort()
        l1 = map(lambda (k, v): (k, v[0]), l1)
        l2 = map(lambda (k, v): (k, v[0]), l2)
        self.assertEqual(l1, l2)
        self.assert_(ob._p_oid != ob2._p_oid)
        self.assertEqual(ob._p_jar, ob2._p_jar)
        oids = {}
        for v in ob.values():
            oids[v._p_oid] = 1
        for v in ob2.values():
            assert not oids.has_key(v._p_oid), (
                'Did not fully separate duplicate from original')
        transaction.commit()

    def testExportImportAborted(self):
        self.testExportImport(abort_it=True)
