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

from goperation.utils import safe_fork

from gopcdn.upload.impl import BaseUpload



LOG = logging.getLogger(__name__)

WEBSOCKETRECVER = 'gopcdn-websocket'


@singleton.singleton
class WebsocketUpload(BaseUpload):


    def upload(self, store, user, group, port,
               rootpath, fileinfo, logfile, exitfunc, timeout):
        logfile = logfile or os.devnull
        executable = systemutils.find_executable(WEBSOCKETRECVER)
        token = str(uuidutils.generate_uuid()).replace('-', '')
        args = [executable, '--home', rootpath, '--token', token, '--port', str(port)]
        args.extend(['--outfile', str(port)])
        args.extend(['--md5', str(port)])
        args.extend(['--crc32', str(port)])
        args.extend(['--size', str(port)])

        changeuser = functools.partial(systemutils.drop_privileges, user, group)

        if self.external_ips:
            ipaddr = self.external_ips[0]
        else:
            ipaddr = self.local_ip
        with logfile as f:
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
            store.setdefault('pid', pid)
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
        _timer = hub.schedule_call_global(3600, _kill)

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
            exitfunc()
            _timer.cancel()

        eventlet.spawn_n(_wait)

        return dict(port=port, token=token, ipaddr=ipaddr)


    def prefunc(self, endpoint):
        endpoint.manager.max_websocket()


    def postfunc(self, endpoint, store, funcs):
        pid = store.get('pid')
        endpoint.manager.websockets.setdefault(pid, WEBSOCKETRECVER)
        funcs.append(lambda : endpoint.manager.websockets.pop(pid, None))

uploader = WebsocketUpload()