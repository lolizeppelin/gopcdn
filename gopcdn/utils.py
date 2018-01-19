import os
from simpleutil.utils import digestutils


def build_fileinfo(path):
    if not os.path.exists(path) or os.path.isdir(path):
        raise ValueError('Path not exist or not file')
    filename = os.path.split(path)[1]
    ext = os.path.splitext(filename)[1][1:]
    fileinfo = {'size': os.path.getsize(path),
                'crc32': digestutils.filecrc32(path),
                'md5': digestutils.filemd5(path),
                'ext': ext,
                'filename': filename}
    return fileinfo
