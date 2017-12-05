import os
import subprocess
try:
    from xml.etree import cElementTree as ET
except ImportError:
    from xml.etree import ElementTree as ET

from simpleutil.utils import jsonutils
from simpleutil.utils import systemutils
from simpleutil.utils import singleton
from simpleutil.log import log as logging

from gopcdn.checkout.impl import BaseCheckOut


LOG = logging.getLogger(__name__)
SVN = systemutils.find_executable('svn')


@singleton.singleton
class SvnCheckOut(BaseCheckOut):

    AUTHSCHEMA = {'type': 'object',
                  'required': ['username', 'password'],
                  'properties':{'username': {'type': 'string'},
                                'password': {'type': 'string'}}
                  }


    def init_conf(self):
        pass

    def checkout(self, uri, auth, version, dst, logfile=None, timeout=None):
        timeout = timeout or self.timeout
        logfile = logfile or os.devnull
        if auth:
            jsonutils.schema_validate(auth, self.AUTHSCHEMA)
        args = [SVN, 'co', '--no-auth-cache', '--trust-server-cert', '--non-interactive',
                uri, '-r']
        if version:
            args.append(version)
        else:
            args.append('HEAD')
        if auth:
            args.extend(('--username %(username)s --password %(password)s' % auth).split(' '))
        args.append(dst)
        LOG.debug('shell execute: %s' % ' '.join(args))
        old_size = systemutils.directory_size(dst, excludes='.svn')
        with open(logfile, 'wb') as f:
            if systemutils.LINUX:
                oldmask = os.umask(0)
                os.umask(022)
            sub = subprocess.Popen(executable=SVN, args=args, stdout=f.fileno(), stderr=f.fileno())
            if systemutils.LINUX:
                os.umask(oldmask)
        systemutils.subwait(sub, timeout)
        return systemutils.directory_size(dst, excludes='.svn') - old_size

    def update(self, auth, version, dst, logfile=None, timeout=None):
        timeout = timeout or self.timeout
        logfile = logfile or os.devnull
        jsonutils.schema_validate(auth, self.AUTHSCHEMA)
        args = [SVN, 'up', '--no-auth-cache', '--trust-server-cert', '--non-interactive', '-r']
        if version:
            args.append(version)
        else:
            args.append('HEAD')
        if auth:
            args.extend([('--username %(username)s -password %(password)s' % auth).split(' ')])
        args.append(dst)
        LOG.debug('shell execute: %s' % ' '.join(args))
        old_size = systemutils.directory_size(dst, excludes='.svn')
        with open(logfile, 'wb') as f:
            if systemutils.LINUX:
                oldmask = os.umask(0)
                os.umask(022)
            sub = subprocess.Popen(executable=SVN, args=args, stdout=f.fileno(), stderr=f.fileno())
            if systemutils.LINUX:
                os.umask(oldmask)
        systemutils.subwait(sub, timeout)
        return systemutils.directory_size(dst, excludes='.svn') - old_size

    def cleanup(self, dst, logfile, timeout=None):
        timeout = timeout or self.timeout
        logfile = logfile or os.devnull
        args = [SVN, 'cleanup', dst]
        LOG.debug('shell execute: %s' % ' '.join(args))
        with open(logfile, 'wb') as f:
            sub = subprocess.Popen(executable=SVN, args=args, stdout=f.fileno(), stderr=f.fileno())
        systemutils.subwait(sub, timeout)

    def getversion(self, dst):
        args = [SVN, 'info', '--xml', dst]
        LOG.debug('shell execute: %s' % ' '.join(args))
        with open(os.devnull, 'wb') as f:
            sub = subprocess.Popen(executable=SVN, args=args, stdout=subprocess.PIPE, stderr=f.fileno())
        try:
            systemutils.subwait(sub, 3)
            xmldata = sub.stdout.read()
        except Exception:
            return None
        finally:
            if not sub.stdout.closed:
                sub.stdout.close()
        if not xmldata:
            return None
        for c in ET.fromstring(xmldata):
            return c.attrib['revision']


checkouter = SvnCheckOut()
