import os
import six
import signal
import nginx
import psutil

from simpleutil.utils import strutils
from simpleutil.utils import systemutils
from simpleutil.utils import singleton

from gopcdn.deploy.exceptions import DeployError
from gopcdn.deploy.impl import BaseDeploy


@singleton.singleton
class NginxDeploy(BaseDeploy):

    def __init__(self):
        super(NginxDeploy, self).__init__()
        self.conf = None
        self.pid = None

    def init_conf(self):
        if os.path.exists(self.root):
            self.conf = nginx.loadf(self.root)
            for server in self.conf.servers:
                keys = server.filter(name='server_name')
                if len(keys) > 1:
                    raise RuntimeError('key of server name more then one')
                hostnames = keys[0].value.strip()
                hostnames = set(strutils.Split(hostnames))
                for hostname in hostnames:
                    if hostname in self.server:
                        raise ValueError('Hostname %s duplicate' % hostname)
                for hostname in hostnames:
                    if not hostname:
                        continue
                    self.server[hostname] = server
                setattr(server, 'elocations', [])
                for key in server.keys:
                    if key.name == 'include':
                        configfile = key.value
                        cf = nginx.loadf(configfile)
                        locations = cf.filter(btype='Location')
                        for l in locations:
                            setattr(l, 'cfile', configfile)
                        server.elocations.extend(locations)
                    if self.hostname in hostnames:
                        if key.name == 'autoindex':
                            if self.autoindex:
                                key.value = 'on'
                        if key.name == 'listen':
                            key.value = self.listen
                        if key.name == 'charset':
                            key.value = self.charset
        else:
            self.conf = nginx.Conf()
            server = nginx.Server()
            server.add(nginx.Key('listen', self.listen),
                       nginx.Key('server_name', self.hostname),
                       nginx.Key('charset', self.charset),
                       nginx.Key('autoindex', 'on' if self.autoindex else 'off'))
            setattr(server, 'elocations', [])
            self.conf.add(server)
            nginx.dumpf(self.conf, self.root)
            self.server[self.hostname] = server

    def find_nginx(self):
        for pid in psutil.pids():
            try:
                p = psutil.Process(pid=pid)
                if p.name() == 'nginx' and p.username() == 'root':
                    self.pid = pid
                    break
            except psutil.NoSuchProcess:
                continue


    def deploy(self, urlpath, cdnhost, rootpath, configfile):
        cdnhost = cdnhost or {}
        if urlpath.endswith('/'):
            urlpath = urlpath[:-1]
        if rootpath.endswith('/'):
            urlpath = rootpath[:-1]
        hostname = cdnhost.get('hostname', self.hostname)
        if hostname not in self.server:
            listen = cdnhost.get('listen', self.listen)
            charset = cdnhost.get('charset', self.charset)
            server = nginx.Server()
            server.add(nginx.Key('listen', listen),
                       nginx.Key('server_name', hostname),
                       nginx.Key('charset', charset),
                       nginx.Key('autoindex', 'on' if self.autoindex else 'off'))
            setattr(server, 'elocations', [])
            self.conf.add(server)
            nginx.dumpf(self.conf, self.root)
            self.server[hostname] = server
        server = self.server[hostname]
        locations = server.elocations
        for l in locations:
            if l.cfile == configfile:
                raise ValueError('config file %s for %s duplicate' % (configfile, hostname))
            if l.value == urlpath:
                raise ValueError('location path %s for %s duplicate' % (urlpath, hostname))
        subconf = nginx.Conf()
        location = nginx.Location(urlpath)
        location.add(nginx.Key('alias', rootpath))
        setattr(location, 'cfile', configfile)
        subconf.add(location)
        nginx.dumpf(subconf, configfile)
        key = nginx.Key('include', configfile)
        server.add(key)
        locations.append(location)
        try:
            nginx.dumpf(self.conf, self.root)
        except Exception:
            server.remove(key)
            os.remove(configfile)
            raise

    def undeploy(self, configfile):
        for server in six.itervalues(self.server):
            locations = server.elocations
            for l in locations:
                if l.cfile == configfile:
                    for key in server.keys:
                        if key.name == 'include' and key.value == l.cfile:
                            server.remove(key)
                            break
                    locations.remove(l)
                    break
        nginx.dumpf(self.conf, self.root)

    def reload(self, raiser=None):
        if systemutils.LINUX:
            for i in range(2):
                try:
                    p = psutil.Process(pid=self.pid)
                    if p.name() != 'nginx' or p.username() != 'root':
                        self.pid = None
                        continue
                    break
                except psutil.NoSuchProcess:
                    pass
            if self.pid:
                os.kill(self.pid, sig=signal.SIGHUP)
            else:
                raise DeployError('nginx reload fail')

    def start(self):
        pass

    def stop(self):
        pass


deployer = NginxDeploy()

deployer.init_conf()


if systemutils.LINUX:
    deployer.find_nginx()
