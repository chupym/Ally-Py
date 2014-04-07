
'''
Created on Jan 5, 2012

@package: ally base
@copyright: 2011 Sourcefabric o.p.s.
@license: http://www.gnu.org/licenses/gpl-3.0.txt
@author: Mugur Rus

Contains the Content Delivery Manager implementation for local file system
'''

import abc
from io import BytesIO
from json.decoder import JSONDecoder
from json.encoder import JSONEncoder
import logging
import os
from os.path import isdir, isfile, join, dirname, abspath
from shutil import copyfile, copyfileobj, move, rmtree
from urllib.parse import urljoin

from ally.cdm.spec import ICDM, UnsupportedProtocol, PathNotFound
from ally.container import wire
from ally.container.ioc import injected
from ally.zip.util_zip import normOSPath, normZipPath


# --------------------------------------------------------------------
log = logging.getLogger(__name__)

# --------------------------------------------------------------------

class IDelivery(metaclass=abc.ABCMeta):
    '''
    Delivery protocol interface
    '''

    @abc.abstractmethod
    def getRepositoryPath(self):
        '''
        Returns the absolute path of the file repository.

        @return: The file repository path
        @rtype: string
        '''

    @abc.abstractmethod
    def getURI(self, repoFilePath):
        '''
        Returns the URI of a certain content identified by the repository path.

        @param repoFilePath: string
            The path of the content item. This is a unique identifier of the item.
        @return: string
            The URI of the content
        '''


@injected
class HTTPDelivery(IDelivery):
    '''
    @ivar serverURI: string
        The server root URI for the static content
    @ivar repositoryPath: string
        The directory where the file repository is
    @see IDelivery
    '''

    serverURI = str
    # The server root URI for the static content

    repositoryPath = str
    # The directory where the file repository is

    def __init__(self):
        assert isinstance(self.serverURI, str), 'Invalid server URI value %s' % self.serverURI
        assert isinstance(self.repositoryPath, str), 'Invalid repository directory value %s' % self.repositoryPath
        self.repositoryPath = normOSPath(self.repositoryPath)
        if not os.path.exists(self.repositoryPath): os.makedirs(self.repositoryPath)
        assert isdir(self.repositoryPath) and os.access(self.repositoryPath, os.W_OK), \
        'Unable to access the repository directory %s' % self.repositoryPath

    def getRepositoryPath(self):
        '''
        @see IDelivery.getRepositoryPath
        '''
        return self.repositoryPath.rstrip(os.sep)

    def getURI(self, repoFilePath):
        '''
        @see IDelivery.getURI
        '''
        assert isinstance(repoFilePath, str), 'Invalid repository file path value %s' % repoFilePath
        serverURI = self.serverURI + '/' if not self.serverURI.endswith('/') else self.serverURI
        return urljoin(serverURI , repoFilePath.lstrip('/'))


@injected
class LocalFileSystemCDM(ICDM):
    '''
    Local file system implementation for the @see: ICDM (Content Delivery Manager interface)
    '''

    delivery = IDelivery
    # The delivery protocol
    cdm_meta_extension = '.~metadata~'; wire.config('cdm_meta_extension', doc='''Extension for cdm metadata files''')
    #Metadata extension

    def __init__(self):
        assert isinstance(self.delivery, IDelivery), 'Invalid delivery protocol %s' % self.delivery

    def getSupportedProtocols(self):
        '''
        @see ICDM.getSupportedProtocols
        '''
        return ('http',)

    def getURI(self, path, protocol='http'):
        '''
        @see ICDM.getURI
        '''
        assert isinstance(path, str), 'Invalid content path %s' % path
        assert isinstance(protocol, str), 'Invalid protocol %s' % protocol
        if protocol == 'http':
            return self.delivery.getURI(path)
        if protocol == 'file':
            return abspath(self._getItemPath(path))
        raise UnsupportedProtocol(protocol)

    def getMetadata(self, path):
        '''
        @see ICDM.getMetadata
        '''
        
        assert isinstance(path, str), 'Invalid content path %s' % path
        path, itemPath = self._validatePath(path)
        if isdir(itemPath) or isfile(itemPath):
            metaItemPath = itemPath + self.cdm_meta_extension
            try:
                with open(metaItemPath, 'r') as metaFile: 
                    metadata = JSONDecoder().decode(metaFile.read())
                return metadata
            except:
                assert log.debug('No CDM metadata found for path {0}.'.format(path), exc_info=1) or True
                return {'createdOn': os.path.getctime(itemPath),
                        'lastModified': os.path.getmtime(itemPath)}
        raise PathNotFound(itemPath)
    # --------------------------------------------------------------------

    def publishFromFile(self, path, filePath, metadata):
        '''
        @see ICDM.publishFromFile
        '''
        assert isinstance(path, str) and len(path) > 0, 'Invalid content path %s' % path
        if not isinstance(filePath, str) and hasattr(filePath, 'read'):
            return self._publishFromFileObj(path, filePath, metadata)
        assert isinstance(filePath, str), 'Invalid file path value %s' % filePath
        path, dstFilePath = self._validatePath(path)
        dstDir = dirname(dstFilePath)
        if not isdir(dstDir):
            os.makedirs(dstDir)
        if not os.access(filePath, os.R_OK):
            raise IOError('Unable to read the file path %s' % filePath)
        
        if not self._isSyncFile(filePath, dstFilePath):
            copyfile(filePath, dstFilePath)
            assert log.debug('Success publishing file %s to path %s', filePath, path) or True
        if metadata:
            self.updateMetadata(path, metadata)
    
    def publishContent(self, path, content, metadata):
        '''
        @see ICDM.publishContent
        '''
        assert isinstance(path, str), 'Invalid content path %s' % path
        path, dstFilePath = self._validatePath(path)
        dstDir = dirname(dstFilePath)
        if not isdir(dstDir):
            os.makedirs(dstDir)
        with open(dstFilePath, 'w+b') as dstFile:
            copyfileobj(content, dstFile)
            assert log.debug('Success publishing content to path %s', path) or True
        if metadata:
            self.updateMetadata(path, metadata)

    def updateMetadata(self, path, metadata):
        '''
        @see ICDM.updateMetadata
        '''
        assert isinstance(path, str), 'Invalid content path %s' % path
        metadataPath = path + self.cdm_meta_extension
        oldMetadata = self.getMetadata(path)
        if oldMetadata: 
            oldMetadata.update(metadata)
            metadata = oldMetadata
        if os.path.exists(path): metadata['lastModified'] = os.path.getmtime(path)
        self.publishFromFile(metadataPath, BytesIO(bytes(JSONEncoder().encode(metadata), 'utf-8')), metadata=None)
        assert log.debug('Success publishing metadata for path %s', path) or True

    def republish(self, oldPath, newPath):
        '''
        @see ICDM.republish
        '''
        oldPath, oldFullPath = self._validatePath(oldPath)
        if isdir(oldFullPath):
            raise PathNotFound(oldPath)
        newPath, newFullPath = self._validatePath(newPath)
        if isdir(newFullPath) or isfile(newFullPath):
            raise ValueError('New path %s is already in use' % newPath)
        dstDir = dirname(newFullPath)
        if not isdir(dstDir):
            os.makedirs(dstDir)
        move(oldFullPath, newFullPath)

    def remove(self, path):
        '''
        @see ICDM.remove
        '''
        path, itemPath = self._validatePath(path)
        if isdir(itemPath):
            rmtree(itemPath)
        elif isfile(itemPath):
            os.remove(itemPath)
            metadataPath = itemPath + self.cdm_meta_extension 
            if isfile(metadataPath):
                os.remove(metadataPath)
        else:
            raise PathNotFound(path)
        assert log.debug('Success removing path %s', path) or True
        
    # --------------------------------------------------------------------
    
    def _publishFromFileObj(self, path, fileObj, metadata):
        '''
        Publish content from a file object

        @param path: string
                The path of the content item. This is a unique
                     identifier of the item.
        @param ioStream: io.IOBase
                The IO stream object
        '''
        assert isinstance(path, str), 'Invalid content path %s' % path
        assert hasattr(fileObj, 'read'), 'Invalid file object %s' % fileObj
        path, dstFilePath = self._validatePath(path)
        dstDir = dirname(dstFilePath)
        if not isdir(dstDir):
            os.makedirs(dstDir)
        with open(dstFilePath, 'w+b') as dstFile:
            copyfileobj(fileObj, dstFile)
            assert log.debug('Success publishing stream to path %s', path) or True
        if metadata:
            self.updateMetadata(path, metadata)

    def _getItemPath(self, path):
        return join(self.delivery.getRepositoryPath(), normOSPath(path.lstrip(os.sep), True))

    def _validatePath(self, path):
        path = normZipPath(path)
        fullPath = normOSPath(self._getItemPath(path), True)
        if not fullPath.startswith(self.delivery.getRepositoryPath()):
            raise PathNotFound(path)
        return (path, fullPath)

    def _isSyncFile(self, srcFilePath, dstFilePath):
        '''
        Return true if the destination file exists and was newer than
        the source file.
        '''
        return ((isfile(srcFilePath) and isfile(dstFilePath)) or \
                (isdir(srcFilePath) and isdir(dstFilePath))) \
                and os.stat(srcFilePath).st_mtime < os.stat(dstFilePath).st_mtime
                
