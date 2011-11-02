import os
import logging
from tempfile import TemporaryFile
from Acquisition import aq_base
from ZODB.interfaces import IBlobStorage
from ZODB.serialize import ObjectWriter
from ZODB.serialize import referencesf
from ZODB.utils import p64, cp
from ZODB.blob import Blob
from ZODB.ExportImport import blob_begin_marker, export_end_marker

logger = logging.getLogger('OFS.ZEXPExport')


def exportZEXP(ob, f=None):
    if f is None:
        f = TemporaryFile()
    elif isinstance(f, str):
        f = open(f,'w+b')
    f.write('ZEXP')

    ob = aq_base(ob)
    oids = []
    
    # Pickle the root object using the RootObjectWriter to make sure that
    # we exclude the oid of the __parent__ from our list of objects to export.
    root_pickler = RootObjectWriter(ob, oids)
    p = root_pickler.serialize(ob)
    f.writelines([ob._p_oid, p64(len(p)), p])

    jar = ob._p_jar
    done_oids = {ob._p_oid: True}
    load=jar._storage.load
    supports_blobs = IBlobStorage.providedBy(jar._storage)
    while oids:
        oid = oids.pop(0)
        if oid in done_oids:
            continue
        done_oids[oid] = True
        try:
            p, serial = load(oid, '')
        except:
            logger.debug("broken reference for oid %s", repr(oid),
                         exc_info=True)
        else:
            referencesf(p, oids)
            f.writelines([oid, p64(len(p)), p])

            if supports_blobs:
                if not isinstance(jar._reader.getGhost(p), Blob):
                    continue # not a blob

                blobfilename = jar._storage.loadBlob(oid, serial)
                f.write(blob_begin_marker)
                f.write(p64(os.stat(blobfilename).st_size))
                blobdata = open(blobfilename, "rb")
                cp(blobdata, f)
                blobdata.close()

    f.write(export_end_marker)
    return f


class RootObjectWriter(ObjectWriter):
    
    def __init__(self, obj, oids):
        ObjectWriter.__init__(self, obj)
        self.parent = aq_base(getattr(obj, '__parent__', None))
        self.oids = oids
    
    def persistent_id(self, obj):
        ref = ObjectWriter.persistent_id(self, obj)
        if ref is not None and obj is not self.parent:
            if isinstance(ref, tuple):
                oid = ref[0]
            elif isinstance(ref, str):
                oid = ref
            else:
                assert isinstance(ref, list)
            self.oids.append(oid)
        return ref
