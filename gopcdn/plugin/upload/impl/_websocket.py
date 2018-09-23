# -*- coding:utf-8 -*-
from simpleutil.log import log as logging
from simpleutil.utils import singleton

from goperation.notify import GeneralNotify
from goperation.websocket import launcher

from gopcdn.plugin.upload.impl import BaseUpload

LOG = logging.getLogger(__name__)

WEBSOCKETPROC = 'gopcdn-websocket'


@singleton.singleton
class WebsocketUpload(BaseUpload):

    def upload(self, user, group, ipaddr, port,
               rootpath, fileinfo, logfile, exitfunc, notify, timeout=None):
        if notify and not isinstance(notify, GeneralNotify):
            raise TypeError('notify not subclass of GeneralNotify')
        if not callable(exitfunc):
            raise TypeError('exitfunc not callable')

        timeout = timeout or self.timeout
        timeout = min(timeout, self.timeout)
        worker = launcher.LaunchWebsocket(WEBSOCKETPROC)
        uri = worker.upload(user, group, ipaddr, port,
                             rootpath, fileinfo, logfile, timeout)
        worker.asyncwait(exitfunc, notify)
        return worker.pid, uri

    @staticmethod
    def prefunc(endpoint):
        endpoint.manager.max_websocket()

    @staticmethod
    def postfunc(endpoint, pid, funcs):
        endpoint.manager.websockets.setdefault(pid, WEBSOCKETPROC)
        funcs.append(lambda: endpoint.manager.websockets.pop(pid, None))


uploader = WebsocketUpload()
