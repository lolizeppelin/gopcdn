import os
import subprocess

from simpleutil.utils import jsonutils
from simpleutil.utils import systemutils
from simpleutil.utils import singleton
from simpleutil.log import log as logging

from gopcdn.checkout.impl import BaseCheckOut


LOG = logging.getLogger(__name__)
SVN = systemutils.find_executable('svn')


@singleton.singleton
class SvnCheckOut(BaseCheckOut):

    AUTHSCHEMA = [{'type': 'null'},
                  {'type': 'object',
                   'required': ['username', 'password'],
                   'properties':{'username': {'type': 'string'},
                                 'password': {'type': 'string'}}}
                  ]

    def init_conf(self):
        pass

    def checkout(self, uri, auth, version, dst, logfile, timeout=None):
        timeout = timeout or self.timeout
        logfile = logfile or os.devnull
        jsonutils.schema_validate(auth, self.AUTHSCHEMA)
        args = [SVN, 'co', '--no-auth-cache', '--trust-server-cert', '--non-interactive',
                uri, '-r']
        if version:
            args.append(version)
        else:
            args.append('HEAD')
        if auth:
            args.extend([('--username %(username)s -password %(password)s' % auth).split(' ')])
        args.append(dst)
        LOG.debug('shell execute: %s' % ' '.join(args))
        with open(logfile, 'wb') as f:
            if systemutils.LINUX:
                mask = os.umask(0)
                os.umask(022)
            sub = subprocess.Popen(executable=SVN, args=args, stdout=f.fileno(), stderr=f.fileno())
            if systemutils.LINUX:
                os.umask(mask)
        systemutils.subwait(sub, timeout)
        return 0

    def update(self, rootpath, version, auth, logfile, timeout=None):
        timeout = timeout or self.timeout
        jsonutils.schema_validate(auth, self.AUTHSCHEMA)
        logfile = logfile or os.devnull
        args = [SVN, 'up', '--no-auth-cache', '--trust-server-cert', '--non-interactive', '-r']
        if version:
            args.append(version)
        else:
            args.append('HEAD')
        if auth:
            args.extend([('--username %(username)s -password %(password)s' % auth).split(' ')])
        args.append(rootpath)
        LOG.debug('shell execute: %s' % ' '.join(args))
        with open(logfile, 'wb') as f:
            sub = subprocess.Popen(executable=SVN, args=args, stdout=f.fileno(), stderr=f.fileno())
        systemutils.subwait(sub, timeout)

    def cleanup(self, rootpath, logfile, timeout=None):
        args = [SVN, 'cleanup', rootpath]
        timeout = timeout or self.timeout
        LOG.debug('shell execute: %s' % ' '.join(args))
        with open(logfile, 'wb') as f:
            sub = subprocess.Popen(executable=SVN, args=args, stdout=f.fileno(), stderr=f.fileno())
        systemutils.subwait(sub, timeout)


checkouter = SvnCheckOut()
