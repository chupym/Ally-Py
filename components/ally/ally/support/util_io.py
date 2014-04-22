'''
Created on Jan 17, 2012

@package: ally base
@copyright: 2011 Sourcefabric o.p.s.
@license: http://www.gnu.org/licenses/gpl-3.0.txt
@author: Gabriel Nistor

Provides utility functions for handling I/O operations.
'''

from ally.zip.util_zip import normOSPath, getZipFilePath, ZIPSEP
from collections import Iterable
from datetime import datetime
from genericpath import isdir, exists
from io import StringIO, BytesIO
from os import stat, makedirs
from os.path import isfile, normpath, join, dirname
from shutil import copy, move
from stat import S_IEXEC
from tempfile import TemporaryDirectory
from zipfile import ZipFile, ZipInfo
import abc
import os
import io
from os import remove

# --------------------------------------------------------------------

class IInputStream(metaclass=abc.ABCMeta):
    '''
    The specification for an input stream.
    '''
    __slots__ = ()

    @abc.abstractclassmethod
    def read(self, nbytes=None):
        '''
        To read a file's contents, call f.read(size), which reads some quantity of data and returns it as a string.
        @param nbytes: integer
            Is an optional numeric argument. When size is omitted or negative, the entire contents of the file will be
            read and returned; it's your problem if the file is twice as large as your machine's memory.
            Otherwise, at most size bytes are read and returned. If the end of the file has been reached, f.read()
            will return an empty string ('').
        @return: bytes
            The content.
        '''

    @classmethod
    def __subclasshook__(cls, C):
        if cls is IInputStream:
            if any('read' in B.__dict__ for B in C.__mro__): return True
        return NotImplemented

class IOutputStream(metaclass=abc.ABCMeta):
    '''
    The specification for an output stream.
    '''
    __slots__ = ()

    @abc.abstractclassmethod
    def write(self, bytes):
        '''
        Write the bytes or bytearray object, b and return the number of bytes written. When in non-blocking mode,
        a BlockingIOError is raised if the buffer needs to be written out but the raw stream blocks.

        @param bytes: bytearray
            The bytes to write.
        '''

    @classmethod
    def __subclasshook__(cls, C):
        if cls is IOutputStream:
            if any('write' in B.__dict__ for B in C.__mro__): return True
        return NotImplemented

class IClosable(metaclass=abc.ABCMeta):
    '''
    Used for the streams that provide a close method.
    '''
    __slots__ = ()

    @abc.abstractclassmethod
    def close(self):
        '''
        Close the stream and block any other operations to the stream.
        '''

    @classmethod
    def __subclasshook__(cls, C):
        if cls is IClosable:
            if any('close' in B.__dict__ for B in C.__mro__): return True
        return NotImplemented
    
class ITeller(metaclass=abc.ABCMeta):
    '''
    Used for the streams that provide a tell method.
    '''
    __slots__ = ()

    @abc.abstractclassmethod
    def tell(self):
        '''
        Provides the stream offset position.
        
        @return: integer
            The stream offset.
        '''

    @classmethod
    def __subclasshook__(cls, C):
        if cls is ITeller:
            if any('tell' in B.__dict__ for B in C.__mro__): return True
        return NotImplemented

# --------------------------------------------------------------------

class IInputStreamClosable(IInputStream, IClosable):
    '''
    Stream specification that also is closable.
    '''
    __slots__ = ()
    
    @classmethod
    def __subclasshook__(cls, C):
        if cls is IInputStreamClosable:
            if (any('read' in B.__dict__ for B in C.__mro__) and
                any('close' in B.__dict__ for B in C.__mro__)): return True
        return NotImplemented

class IInputStreamTeller(IInputStream, ITeller):
    '''
    Stream specification that also tells the stream offset.
    '''
    __slots__ = ()
    
    @classmethod
    def __subclasshook__(cls, C):
        if cls is IInputStreamTeller:
            if (any('read' in B.__dict__ for B in C.__mro__) and
                any('tell' in B.__dict__ for B in C.__mro__)): return True
        return NotImplemented
    
class IInputStreamCT(IInputStream, IClosable, ITeller):
    '''
    Stream specification that also is closable and tells the stream offset.
    '''
    __slots__ = ()
    
    @classmethod
    def __subclasshook__(cls, C):
        if cls is IInputStreamCT:
            if (any('read' in B.__dict__ for B in C.__mro__) and
                any('close' in B.__dict__ for B in C.__mro__) and
                any('tell' in B.__dict__ for B in C.__mro__)): return True
        return NotImplemented
    
# --------------------------------------------------------------------

def keepOpen(stream):
    '''
    Keeps opened a stream, basically blocks the close calls.
    
    @param stream: IInputStream
        The stream to keep open.
    @return: IInputStream
        The stream wrapper that prevent closing.
    '''
    assert isinstance(stream, IInputStream), 'Invalid stream %s' % stream
    if not isinstance(stream, IClosable): return stream
    return KeepOpen(stream)

def tellPosition(stream):
    '''
    Provides a stream that keeps track of the number of bytes that are read from the stream.
    
    @param stream: IInputStream
        The stream to keep track for.
    @return: IInputStreamTeller
        The stream that provides the tell method.
    '''
    assert isinstance(stream, IInputStream), 'Invalid stream %s' % stream
    if isinstance(stream, ITeller):
        assert isinstance(stream, ITeller)
        try: stream.tell()
        except io.UnsupportedOperation: pass  # Event if tell is available the action itself is not possible.
        else: return stream
    return TellPosition(stream)
    
def pipe(srcFileObj, dstFileObj, bufferSize=1024):
    '''
    Copy the content from a source file to a destination file

    @param srcFileObj: a file like object with a 'read' method
        The file object to copy from
    @param dstFileObj: a file like object with a 'write' method
        The file object to copy to
    @param bufferSize: integer
        The buffer size used for copying data chunks.
    '''
    assert isinstance(srcFileObj, IInputStream), 'Invalid source file object %s' % srcFileObj
    assert isinstance(dstFileObj, IOutputStream), 'Invalid destination file object %s' % dstFileObj
    assert isinstance(bufferSize, int), 'Invalid buffer size %s' % bufferSize
    while True:
        buffer = srcFileObj.read(bufferSize)
        if not buffer: break
        dstFileObj.write(buffer)

def readGenerator(fileObj, bufferSize=1024):
    '''
    Provides a generator that read data from the provided file object.

    @param fileObj: a file like object with a 'read' method
        The file object to have the generator read data from.
    @param bufferSize: integer
        The buffer size used for returning data chunks.
    '''
    assert isinstance(fileObj, IInputStream), 'Invalid file object %s' % fileObj
    assert isinstance(bufferSize, int), 'Invalid buffer size %s' % bufferSize

    try:
        while True:
            buffer = fileObj.read(bufferSize)
            if not buffer: break
            yield buffer
    finally:
        if isinstance(fileObj, IClosable): fileObj.close()

def writeGenerator(generator, fileObj):
    '''
    Provides a generator that read data from the provided file object.

    @param generator: Iterable
        The generator to get the content to be writen.
    @param fileObj: IOutputStream, a file like object with a 'write' method
        The file object to have the generator write data from.
    @return: IOutputStream
        The same file object.
    '''
    assert isinstance(generator, Iterable), 'Invalid generator %s' % generator
    assert isinstance(fileObj, IOutputStream), 'Invalid file object %s' % fileObj
    assert isinstance(fileObj, IClosable), 'Invalid file object %s' % fileObj

    for bytes in generator: fileObj.write(bytes)
    return fileObj

def convertToBytes(iterable, charSet, encodingError):
    '''
    Provides a generator that converts from string to bytes based on string data from another Iterable.

    @param iterable: Iterable
        The iterable providing the strings to convert.
    @param charSet: string
        The character set to encode based on.
    @param encodingError: string
        The encoding error resolving.
    '''
    assert isinstance(iterable, Iterable), 'Invalid iterable %s' % iterable
    assert isinstance(charSet, str), 'Invalid character set %s' % charSet
    assert isinstance(encodingError, str), 'Invalid encoding error set %s' % encodingError
    for value in iterable:
        assert isinstance(value, str), 'Invalid value %s received' % value
        yield value.encode(encoding=charSet, errors=encodingError)
        
# TODO: Gabriel: In the future this will become absollete when using the setup distutils proper packaging.
def openURI(path, byteMode=True):
    '''
    Returns a read file object for the given path.

    @param path: string
        The path to a resource: a file system path, a ZIP path
    @return: byte file
        A file like object that delivers bytes.
    '''
    path = normOSPath(path)
    mode = 'rb' if byteMode else 'rt'
    if isfile(path): return open(path, mode)
    zipFilePath, inZipPath = getZipFilePath(path)
    zipFile = ZipFile(zipFilePath)
    if inZipPath in zipFile.NameToInfo and not inZipPath.endswith(ZIPSEP) and inZipPath != '':
        f = zipFile.open(inZipPath)
        if byteMode: return f
        else: return StringIO(f.read().decode())
    raise IOError('Invalid file path %s' % path)

# TODO: Gabriel: In the future this will become absollete when using the setup distutils proper packaging.
def timestampURI(path):
    '''
    Returns the last modified time stamp for the given path.

    @param path: string
        The path to a resource: a file system path, a ZIP path
    @return: datetime
        The last modified time stamp.
    '''
    path = normOSPath(path)
    if isfile(path):
        return datetime.fromtimestamp(stat(path).st_mtime)
    zipFilePath, _inZipPath = getZipFilePath(path)
    return datetime.fromtimestamp(stat(zipFilePath).st_mtime)

# TODO: Gabriel: In the future this will become absollete when using the setup distutils proper packaging.
def synchronizeURIToDir(path, dirPath):
    '''
    Publishes the entire contents from the URI path to the provided directory path.

    @param path: string
        The path to a resource: a file system path, a ZIP path
    @param dirPath: string
        The directory path to synchronize with.
    '''
    assert isinstance(path, str) and path, 'Invalid content path %s' % path
    assert isinstance(dirPath, str), 'Invalid directory path value %s' % dirPath

    if not isdir(path):
        # not a directory, see if it's a entry in a zip file
        zipFilePath, inDirPath = getZipFilePath(path)
        zipFile = ZipFile(zipFilePath)
        if not inDirPath.endswith(ZIPSEP): inDirPath = inDirPath + ZIPSEP

        tmpDir = TemporaryDirectory()

        lenPath, zipTime = len(inDirPath), datetime.fromtimestamp(stat(zipFilePath).st_mtime)
        for zipInfo in zipFile.filelist:
            assert isinstance(zipInfo, ZipInfo), 'Invalid zip info %s' % zipInfo
            if zipInfo.filename.startswith(inDirPath):
                if zipInfo.filename[0] == '/': dest = zipInfo.filename[1:]
                else: dest = zipInfo.filename

                dest = normpath(join(dirPath, dest[lenPath:]))

                if exists(dest) and zipTime <= datetime.fromtimestamp(stat(dest).st_mtime): continue
                destDir = dirname(dest)
                if not exists(destDir): makedirs(destDir)

                zipFile.extract(zipInfo.filename, tmpDir.name)
                move(join(tmpDir.name, normOSPath(zipInfo.filename)), dest)
                if zipInfo.filename.endswith('.exe'): os.chmod(dest, stat(dest).st_mode | S_IEXEC)
        return

    path = normpath(path)
    assert os.access(path, os.R_OK), 'Unable to read the directory path %s' % path
    lenPath = len(path) + 1
    for root, _dirs, files in os.walk(path):
        for file in files:
            src, dest = join(root, file), join(dirPath, root[lenPath:], file)

            if exists(dest) and \
            datetime.fromtimestamp(stat(src).st_mtime) <= datetime.fromtimestamp(stat(dest).st_mtime): continue

            destDir = dirname(dest)
            if not exists(destDir): makedirs(destDir)
            copy(src, dest)
            if file.endswith('.exe'): os.chmod(dest, stat(dest).st_mode | S_IEXEC)

class KeepOpen(IInputStreamClosable):
    '''
    Keeps opened a stream, basically blocks the close calls.
    '''
    __slots__ = ('_stream',)

    def __init__(self, stream):
        '''
        Construct the keep open stream.

        @param stream: IInputStreamClosable
            A stream to keep open.
        '''
        assert isinstance(stream, IInputStreamClosable), 'Invalid stream %s' % stream
        self._stream = stream
        
    def read(self, nbytes=None):
        '''
        @see: IInputStreamClosable.read
        '''
        return self._stream.read(nbytes)

    def close(self):
        '''
        @see: IInputStreamClosable.close
        Block the close action.
        '''
        
class TellPosition(IInputStreamCT):
    '''
    Provides a stream that keeps track of the number of bytes that are read from the stream.
    '''
    __slots__ = ('_stream', '_offset')

    def __init__(self, stream):
        '''
        Construct the tell position stream.

        @param stream: IInputStream
            The stream to keep track of.
        '''
        assert isinstance(stream, IInputStream), 'Invalid stream %s' % stream
        self._stream = stream
        self._offset = 0
        
    def read(self, nbytes=None):
        '''
        @see: IInputStreamCT.read
        '''
        bytes = self._stream.read(nbytes)
        self._offset += len(bytes)
        return bytes
    
    def tell(self):
        '''
        @see: IInputStreamCT.tell
        '''
        return self._offset

    def close(self):
        '''
        @see: IInputStreamCT.close
        '''
        if isinstance(self._stream, IClosable): self._stream.close()

class StreamOnIterable(IInputStreamClosable):
    '''
    An implementation for a @see: IInputStream that uses as a source a generator that yileds bytes.
    '''
    __slots__ = ('_generator', '_closed', '_done', '_source')
    
    def __init__(self, generator):
        '''
        Construct the stream from generator.
        
        @param generator: Iterable(bytes)
            The generator that yileds bytes that will be used as the stream source.
        '''
        assert isinstance(generator, Iterable), 'Invalid generator %s' % generator
        
        self._generator = iter(generator)
        self._closed = False
        self._done = False
        self._source = BytesIO()
        
    def read(self, nbytes=None):
        '''
        @see: IInputStreamClosable.read
        '''
        if self._closed: raise ValueError('I/O operation on closed stream.')
        if self._done: return b''
        if nbytes:
            assert isinstance(nbytes, int), 'Invalid number of bytes required %s' % nbytes
            if nbytes < 0: nbytes = None
            elif nbytes == 0: return b''
            
        if nbytes is None:
            while True:
                try: bytes = next(self._generator)
                except StopIteration: break
                self._source.write(bytes)
            self._done = True
            return self._source.getvalue()
        
        if self._source.tell() == nbytes:
            value = self._source.getvalue()
            self._source.seek(0)
            self._source.truncate()
        elif self._source.tell() > nbytes:
            self._source.seek(0)
            value = self._source.read(nbytes)
            remaining = self._source.read()
            self._source.truncate()
            self._source.write(remaining)
        else:
            while True:
                try: bytes = next(self._generator)
                except StopIteration:
                    value = self._source.getvalue()
                    self._done = True
                    break
                self._source.write(bytes)
                if self._source.tell() == nbytes:
                    # We have the correct size
                    value = self._source.getvalue()
                    self._source.seek(0)
                    self._source.truncate()
                    break
                elif self._source.tell() > nbytes:
                    self._source.seek(0)
                    value = self._source.read(nbytes)
                    remaining = self._source.read()
                    self._source.truncate()
                    self._source.write(remaining)
                    break
        return value
        
    def close(self):
        '''
        @see: IInputStreamClosable.close
        '''
        self._closed = True

class ReplaceInStream(IInputStreamClosable):
    '''
    Provides the file read replacing.
    '''
    __slots__ = ('_stream', '_replacements', '_maxKey', '_leftOver')

    def __init__(self, stream, replacements):
        '''
        Creates a proxy for the provided file object that will replace in the provided file content based on the data
        provided in the replacements map.

        @param fileObj: a file like object with a 'read' method
            The file object to wrap and have the content changed.
        @param replacements: dictionary{string|bytes, string|bytes}
            A dictionary containing as a key the data that needs to be changed and as a value the data to change with.
        @return: Proxy
            The proxy created for the file that will handle the data replacing.
        '''
        assert isinstance(stream, IInputStream), 'Invalid stream %s' % stream
        assert isinstance(replacements, dict), 'Invalid replacements %s' % replacements
        if __debug__:
            for key, value in replacements.items():
                assert isinstance(key, (str, bytes)), 'Invalid key %s' % key
                assert isinstance(value, (str, bytes)), 'Invalid value %s' % value
        self._stream = stream
        self._replacements = replacements

        self._maxKey = len(max(replacements.keys(), key=lambda v: len(v)))
        self._leftOver = None

    def read(self, nbytes=None):
        '''
        @see: IInputStreamClosable.read
        '''
        if nbytes is None: data = self._stream.read()
        else: data = self._stream.read(nbytes)

        if not data:
            if self._leftOver:
                data = self._leftOver
                self._leftOver = None
            else: return data

        toIndex = None
        if self._leftOver:
            toIndex = len(data)
            data = self._leftOver + data
        else:
            extra = self._stream.read(self._maxKey - 1)
            if extra:
                toIndex = len(data)
                data = data + extra

        for key, value in self._replacements.items(): data = data.replace(key, value)

        if toIndex:
            self._leftOver = data[toIndex:]
            data = data[:toIndex]

        return data
    
    def close(self):
        '''
        @see: IInputStreamClosable.close
        '''
        if isinstance(self._stream, IClosable): self._stream.close()

class TempFile:
    '''
    Context manager for temporary files.
    '''
    def __init__(self, filePath):
        assert isinstance(filePath, str) and isfile(filePath), 'Invalid file path %s' % filePath
        self.filePath = filePath
    
    def __enter__(self):
        pass
    
    def __exit__(self, exc_type, exc_val, exc_tb):
        if isfile(self.filePath):
            remove(self.filePath)
