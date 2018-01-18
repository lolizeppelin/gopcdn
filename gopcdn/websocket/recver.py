# -*- coding:utf-8 -*-
import os
import time
import select
import sys
import errno
import logging
import zlib
import requests
import hashlib
from simpleutil.utils import jsonutils

import eventlet
from six.moves import http_cookies as Cookie
from websockify import websocket

try:
    from http.server import SimpleHTTPRequestHandler
except:
    from SimpleHTTPServer import SimpleHTTPRequestHandler

try:
    from cStringIO import StringIO
except ImportError:
    from StringIO import StringIO

from simpleutil.config import cfg


from goperation.websocket.base import GopWebSocketServerBase

CONF = cfg.CONF


recver_opts = [
    cfg.StrOpt('outfile',
               required=True,
               short='o',
               help='webesocket recver output file'),
    cfg.StrOpt('md5',
               required=True,
               help='file md5 value'),
    cfg.IntOpt('crc32',
               required=True,
               help='file crc32 value, int'),
    cfg.IntOpt('size',
               required=True,
               help='file size'),
    ]


class FileRecvRequestHandler(websocket.WebSocketRequestHandler):

    def __init__(self, req, addr, server):
        self.lastrecv = 0
        if os.path.exists(CONF.outfile):
            raise RuntimeError('output file %s alreday exist' % CONF.outfile)
        self.timeout = CONF.heartbeat * 3
        websocket.WebSocketRequestHandler.__init__(self, req, addr, server)

    def do_GET(self):
        # hcookie = self.headers.getheader('cookie')
        # if hcookie:
        #     cookie = Cookie.SimpleCookie()
        #     cookie.load(hcookie)
        #     if 'token' in cookie:
        #         token = cookie['token'].value


        if not self.handle_websocket():
            self.send_error(405, "Method Not Allowed")

    def new_websocket_client(self):
        size = 0
        crc = 0
        md5 = hashlib.md5()
        self.close_connection = 1
        # cancel suicide
        logging.info('suicide cancel, start recv buffer')
        self.server.suicide.cancel()
        rlist = [self.request]
        wlist = []
        success = False
        outfile = CONF.outfile
        self.lastrecv = int(time.time())
        with open(outfile, 'wb') as f:
            while True:
                if size >= CONF.size:
                    break
                if int(time.time()) - self.lastrecv > CONF.heartbeat:
                    logging.error('Over heartbeat time')
                    break
                try:
                    ins, outs, excepts = select.select(rlist, wlist, [], 1.0)
                except (select.error, OSError):
                    exc = sys.exc_info()[1]
                    if hasattr(exc, 'errno'):
                        err = exc.errno
                    else:
                        err = exc[0]
                    if err != errno.EINTR:
                        raise
                    else:
                        eventlet.sleep(0.01)
                        continue
                if excepts:
                    raise Exception("Socket exception")

                if self.request in ins:
                    # Receive client data, decode it, and queue for target
                    bufs, closed = self.recv_frames()
                    if bufs:
                        self.lastrecv = int(time.time())
                        for buf in bufs:
                            if buf:
                                crc = zlib.crc32(buf, crc)
                                md5.update(buf)
                                f.write(buf)
                                size += len(buf)
                    if closed:
                        logging.info('Client send close')
                        break

        if size == CONF.size:
            md5 = md5.hexdigest()
            if CONF.md5 == md5 and CONF.crc32 == crc:
                success = True

        if not success:
            logging.error('upload file fail, delete it')
            if os.path.exists(outfile):
                os.remove(outfile)
            logging.error('need size %d, recv %d' % (CONF.size, size))
            logging.error('need md5 %s, recv %d' % (CONF.md5, md5))
            logging.error('need crc32 %s, recv %d' % (CONF.crc32, crc))


class FileRecvWebSocketServer(GopWebSocketServerBase):
    def __init__(self):
        super(FileRecvWebSocketServer, self).__init__(RequestHandlerClass=FileRecvRequestHandler)
