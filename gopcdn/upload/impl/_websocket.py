# -*- coding:utf-8 -*-
import os
import sys
import functools
import subprocess
import psutil
import eventlet
from eventlet import hubs

from simpleutil.utils import uuidutils
from simpleutil.utils import systemutils
from simpleutil.utils import singleton
from simpleutil.log import log as logging

import goperation
from goperation.utils import safe_fork

from gopcdn.upload.impl import BaseUpload


LOG = logging.getLogger(__name__)

WEBSOCKETRECVER = 'gopcdn-websocket'


@singleton.singleton
class WebsocketUpload(BaseUpload):
    def upload(self, user, group, ipaddr, port,
               rootpath, fileinfo, logfile, exitfunc, notify, timeout):
        if timeout:
            timeout = int(timeout)
        if timeout > 7200:
            raise ValueError('Timeout over 7200 seconds')
        with goperation.tlock('gopcdn-websocket-upload'):
            logfile = logfile or os.devnull
            executable = systemutils.find_executable(WEBSOCKETRECVER)
            token = str(uuidutils.generate_uuid()).replace('-', '')
            args = [executable, '--home', rootpath, '--token', token, '--port', str(port)]

            ext = fileinfo.get('ext')
            filename = fileinfo.get('filename')
            overwrite = fileinfo.get('overwrite')

            if overwrite:
                # 确认需要覆盖对象
                overwrite = os.path.join(rootpath, overwrite)
                if not os.path.exists(overwrite):
                    raise ValueError('Overwrite not exit')
                if os.path.isdir(overwrite):
                    raise ValueError('overwrite target is dir')
                if not os.access(overwrite, os.W_OK):
                    raise ValueError('overwrite target not writeable')

            # 判断文件是否存在
            filename = os.path.join(rootpath, filename)
            if os.path.exists(filename):
                if os.path.isdir(filename):
                    raise ValueError('Can not cover dir from file')
                if overwrite != filename:
                    raise ValueError('file exist with same name')
            # 准备文件目录
            path = os.path.split(filename)[0]
            if not os.path.exists(path):
                os.makedirs(path, mode=0775)
                os.chown(path, user, group)
            else:
                if not os.path.isdir(path):
                    raise ValueError('prefix path is not dir')

            if not ext or ext == 'tmp':
                raise ValueError('Can not find file ext or ext is tmp')
            # 临时文件名
            _tempfile = os.path.join(rootpath, '%s.tmp' % str(uuidutils.generate_uuid()).replace('-', ''))
            args.extend(['--outfile', _tempfile])
            args.extend(['--md5', fileinfo.get('md5')])
            args.extend(['--crc32', fileinfo.get('crc32')])
            args.extend(['--size', str(fileinfo.get('size'))])

            changeuser = functools.partial(systemutils.drop_privileges, user, group)

            with open(logfile, 'wb') as f:
                LOG.debug('Websocket command %s %s' % (executable, ' '.join(args)))
                if systemutils.POSIX:
                    sub = subprocess.Popen(executable=executable, args=args,
                                           stdout=f.fileno(), stderr=f.fileno(),
                                           close_fds=True, preexec_fn=changeuser)
                    pid = sub.pid
                else:
                    pid = safe_fork(user=user, group=group)
                    if pid == 0:
                        os.dup2(f.fileno(), sys.stdout.fileno())
                        os.dup2(f.fileno(), sys.stderr.fileno())
                        os.closerange(3, systemutils.MAXFD)
                        os.execv(executable, args)
                self.pid = pid
                LOG.info('Websocket recver start with pid %d' % pid)

            def _kill():
                try:
                    p = psutil.Process(pid=pid)
                    name = p.name()
                except psutil.NoSuchProcess:
                    return
                if name == WEBSOCKETRECVER:
                    LOG.warning('Websocket recver overtime, kill it')
                    p.kill()

            hub = hubs.get_hub()
            _timer = hub.schedule_call_global(timeout or 3600, _kill)

            def _wait():
                try:
                    if systemutils.POSIX:
                        from simpleutil.utils.systemutils import posix
                        posix.wait(pid)
                    else:
                        systemutils.subwait(sub)
                except Exception as e:
                    LOG.error('Websocket recver wait catch error %s' % str(e))
                LOG.info('Websocket recver with pid %d has been exit' % pid)
                _timer.cancel()
                exitfunc()
                if not os.path.exists(_tempfile) \
                        or (os.path.getsize(_tempfile) != fileinfo.get('size')):
                    LOG.error('Upload file fail, file not exist')
                    if os.path.exists(_tempfile):
                        os.remove(_tempfile)
                    notify.fail()
                    return
                if overwrite:
                    os.remove(overwrite)
                LOG.info('Upload file end, success')
                os.rename(_tempfile, filename)
                notify.success()

            eventlet.spawn_n(_wait)

            return dict(port=port, token=token, ipaddr=ipaddr)


    def prefunc(self, endpoint):
        endpoint.manager.max_websocket()

    def postfunc(self, endpoint, funcs):
        if self.pid:
            pid = self.pid
            self.pid = None
            funcs.append(lambda: endpoint.manager.websockets.pop(pid, None))
            endpoint.manager.websockets.setdefault(pid, WEBSOCKETRECVER)


uploader = WebsocketUpload()