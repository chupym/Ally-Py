'''
Created on Apr 11, 2012

@package: ally base
@copyright: 2011 Sourcefabric o.p.s.
@license: http://www.gnu.org/licenses/gpl-3.0.txt
@author: Gabriel Nistor

Provide support classes for the CDM handling.
'''

from .spec import ICDM
from os.path import join, isfile
import os
import time
from shutil import copyfile
from ally.zip.util_zip import normOSPath, normZipPath

# --------------------------------------------------------------------

class VersioningCDM(ICDM):
    '''
    Provides a CDM that delegates the call to a wrapped CDM but before that it does some file versioning.
    @see: ICDM
    '''
    
    def __init__(self, wrapped):
        '''
        Construct the extend path CDM.
        
        @param wrapped: ICDM
            The wrapped CDM.
        @param format: string
            The format to apply to the path before being delivered to the wrapped CDM, something like 'my_root_folder/%s'
        '''
        assert isinstance(wrapped, ICDM), 'Invalid wrapped CDM %s' % wrapped
        self.wrapped = wrapped
        
    def publishFromFile(self, path, filePath, metadata=None):
        '''
        @see: ICDM.publishFromFile
        '''
        #get the full path on the repository for the file
        fullPath = join(self.wrapped.delivery.getRepositoryPath(), normOSPath(path.lstrip(os.sep), True))
        #if file already exists, we will add a new version
        fileExists = isfile(fullPath)
        path = normZipPath(path)
        
        self.wrapped.publishFromFile(path, filePath, metadata)
        
        if fileExists:
            metadata = self.wrapped.getMetadata(path)
            #make a new version of the file
            versionPath = '%s_%s%s' % (path[:path.rfind('.')],\
                        str(int(time.time())),\
                        path[path.rfind('.'):])
            
            fullVersionPath = join(fullPath[:fullPath.rfind(path)], versionPath)
            copyfile(fullPath, fullVersionPath)
            #update the metadata
            self.wrapped.updateMetadata(path, {'lastVersion':versionPath})
            
            #now delete old version of the file
            oldVersion = metadata.get('lastVersion', False)
            if oldVersion:
                os.remove(join(self.wrapped.delivery.getRepositoryPath(), normOSPath(oldVersion.lstrip(os.sep), True)))
        
    def publishFromDir(self, path, dirPath):
        '''
        @see: ICDM.publishFromDir
        '''
        self.wrapped.publishFromDir(path, dirPath)

    def publishContent(self, path, content, metadata):
        '''
        @see: ICDM.publishContent
        '''
        self.wrapped.publishContent(path, content, metadata)
        
    def copyLocal(self, path, localPath):
        '''
        @see ICDM.copyLocal
        '''
        self.wrapped.copyLocal(path, localPath)

    def updateMetadata(self, path, metadata):
        '''
        @see: ICDM.publishMetadata
        '''
        self.wrapped.updateMetadata(path, metadata)
        
    def republish(self, oldPath, newPath):
        '''
         @see: ICDM.republish
        '''    
        self.wrapped.republish(oldPath, newPath)

    def remove(self, path):
        '''
        @see: ICDM.remove
        '''
        self.wrapped.remove(path)

    def getSupportedProtocols(self):
        '''
        @see: ICDM.getSupportedProtocols
        '''
        return self.wrapped.getSupportedProtocols()

    def getURI(self, path, protocol='http'):
        '''
        @see: ICDM.getURI
        '''
        #return the path of the last version of the file (if any) or the path of the file itself
        return self.wrapped.getURI(self.wrapped.getMetadata(path).get('lastVersion', path), protocol)

    def getMetadata(self, path):
        '''
        @see ICDM.getMetadata
        '''
        return self.wrapped.getMetadata(path)


class ExtendPathCDM(ICDM):
    '''
    Provides a CDM that delegates the call to a wrapped CDM but before that it alters the path.
    @see: ICDM
    '''

    def __init__(self, wrapped, format):
        '''
        Construct the extend path CDM.
        
        @param wrapped: ICDM
            The wrapped CDM.
        @param format: string
            The format to apply to the path before being delivered to the wrapped CDM, something like 'my_root_folder/%s'
        '''
        assert isinstance(wrapped, ICDM), 'Invalid wrapped CDM %s' % wrapped
        assert isinstance(format, str), 'Invalid path format %s' % format
        self.wrapped = wrapped
        self.format = format

    def publishFromFile(self, path, filePath, metadata):
        '''
        @see: ICDM.publishFromFile
        '''
        self.wrapped.publishFromFile(self.format % path, filePath, metadata)

    def publishContent(self, path, content, metadata):
        '''
        @see: ICDM.publishContent
        '''
        self.wrapped.publishContent(self.format % path, content, metadata)
        
    def copyLocal(self, path, localPath):
        '''
        @see ICDM.copyLocal
        '''
        self.wrapped.copyLocal(self.format % path, localPath)

    def updateMetadata(self, path, metadata):
        '''
        @see: ICDM.publishMetadata
        '''
        self.wrapped.updateMetadata(self.format % path, metadata)

    def republish(self, oldPath, newPath):
        '''
         @see: ICDM.republish
        '''    
        self.wrapped.republish(self.format % oldPath, self.format % newPath)

    def remove(self, path):
        '''
        @see: ICDM.remove
        '''
        self.wrapped.remove(self.format % path)

    def getSupportedProtocols(self):
        '''
        @see: ICDM.getSupportedProtocols
        '''
        return self.wrapped.getSupportedProtocols()

    def getURI(self, path, protocol='http'):
        '''
        @see: ICDM.getURI
        '''
        return self.wrapped.getURI(self.format % path, protocol)

    def getMetadata(self, path):
        '''
        @see ICDM.getMetadata
        '''
        return self.wrapped.getMetadata(self.format % path)
