# -*- coding:utf-8 -*-
import os
import time
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
RSYNC = systemutils.find_executable('rsync')


@singleton.singleton
class SvnCheckOut(BaseCheckOut):

    AUTHSCHEMA = {'type': 'object',
                  'required': ['uri', 'username', 'password'],
                  'properties':{'uri': {'type': 'string'},
                                'username': {'type': 'string'},
                                'password': {'type': 'string'}}
                  }


    def init_conf(self):
        pass

    def copy(self, src, dst, **kwargs):
        timeout = kwargs.get('timeout') or self.timeout
        LOG.info('Try copy from %s to %s' % (src, dst))
        prerun = kwargs.pop('prerun', None)
        src = src + os.sep
        dst = dst + os.sep
        args = [RSYNC, '-qdr', '--exclude=.svn']
        args.append(src)
        args.append(dst)
        with open(os.devnull, 'rb') as f:
            if systemutils.LINUX:
                oldmask = os.umask(0)
                os.umask(022)
            sub = subprocess.Popen(executable=RSYNC, args=args, stdout=f.fileno(), stderr=f.fileno(),
                                   preexec_fn=prerun)
            if systemutils.LINUX:
                os.umask(oldmask)
        systemutils.subwait(sub, timeout)

    def checkout(self, auth, version, dst, logfile, timeout, **kwargs):
        """资源检出, 不存在svn信息调用svn checkout 否则调用svn update"""
        if self.getversion(dst) is None:
            return self._checkout(auth, version, dst, logfile, timeout)
        else:
            return self._update(auth, version, dst, logfile, timeout)

    def _checkout(self, auth, version, dst, logfile=None, timeout=None, **kwargs):
        prerun = kwargs.pop('prerun', None)
        timeout = timeout or self.timeout
        logfile = logfile or os.devnull
        if auth:
            jsonutils.schema_validate(auth, self.AUTHSCHEMA)
        uri = auth['uri']
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
            sub = subprocess.Popen(executable=SVN, args=args, stdout=f.fileno(), stderr=f.fileno(),
                                   preexec_fn=prerun)
            if systemutils.LINUX:
                os.umask(oldmask)
        systemutils.subwait(sub, timeout)
        return systemutils.directory_size(dst, excludes='.svn') - old_size

    def _update(self, auth, version, dst, logfile=None, timeout=None, **kwargs):
        prerun = kwargs.pop('prerun', None)
        timeout = timeout or self.timeout
        logfile = logfile or os.devnull
        jsonutils.schema_validate(auth, self.AUTHSCHEMA)
        args = [SVN, 'up', '--no-auth-cache', '--trust-server-cert', '--non-interactive', '-r']
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
            sub = subprocess.Popen(executable=SVN, args=args, stdout=f.fileno(), stderr=f.fileno(), close_fds=True,
                                   preexec_fn=prerun)
            if systemutils.LINUX:
                os.umask(oldmask)
        systemutils.subwait(sub, timeout)
        return systemutils.directory_size(dst, excludes='.svn') - old_size

    def cleanup(self, dst, logfile, timeout=None, **kwargs):
        prerun = kwargs.pop('prerun', None)
        timeout = timeout or self.timeout
        logfile = logfile or os.devnull
        args = [SVN, 'cleanup', dst]
        LOG.debug('shell execute: %s' % ' '.join(args))
        with open(logfile, 'wb') as f:
            sub = subprocess.Popen(executable=SVN, args=args,
                                   stdout=f.fileno(), stderr=f.fileno(), close_fds=True,
                                   preexec_fn=prerun)
        systemutils.subwait(sub, timeout)

    def getversion(self, dst, **kwargs):
        prerun = kwargs.pop('prerun', None)
        args = [SVN, 'info', '--xml', dst]
        LOG.debug('shell execute: %s' % ' '.join(args))
        with open(os.devnull, 'wb') as f:
            sub = subprocess.Popen(executable=SVN, args=args,
                                   stdout=subprocess.PIPE, stderr=f.fileno(), close_fds=True,
                                   preexec_fn=prerun)
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
