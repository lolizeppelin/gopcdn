# -*- coding:utf-8 -*-
from simpleutil.config import cfg
from simpleutil.utils import importutils

CONF = cfg.CONF


def uploader(impl):
    """资源上传, 默认上传工具websocket"""
    obj = 'gopcdn.upload.plugin.impl._%s.uploader' % impl
    return importutils.import_class(obj)
