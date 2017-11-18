import os
import re
import nginx
from simpleutil.utils import singleton

from gopcdn.deploy.impl import BaseDeploy


Split = re.compile(r'\s').split


@singleton.singleton
class NginxDeploy(BaseDeploy):

    def __init__(self):
        super(NginxDeploy, self).__init__()
        self.conf = None

    def init_conf(self):
        if os.path.exists(self.root):
            self.conf = nginx.loadf(self.root)
            for server in self.conf.servers:
                keys = server.filter(name='server_name')
                if len(keys) > 1:
                    raise
                hostnames = keys[0].value.strip()
                hostnames = set(Split(hostnames))
                for hostname in hostnames:
                    if hostname in self.server:
                        raise ValueError('Hostname %s duplicate' % hostname)
                for hostname in hostnames:
                    if not hostname:
                        continue
                    self.server[hostname] = server
                for key in server.keys:
                    if key.name == 'include':
                        configfile = key.value
                        cf = nginx.loadf(configfile)
                        locations = cf.filter(btype='Location')
                        for l in locations:
                            setattr(l, 'cfile', configfile)
                        server.add(*locations)
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
            self.conf.add(server)
            nginx.dumpf(self.conf, self.root)
            self.server[self.hostname] = server

    def deploy(self, urlpath, rootpath, configfile, hostinfo=None):
        hostinfo = hostinfo or {}
        if urlpath.endswith('/'):
            urlpath = urlpath[:-1]
        if rootpath.endswith('/'):
            urlpath = rootpath[:-1]
        hostname = hostinfo.get('hostname', self.hostname)
        if hostname not in self.server:
            listen = hostinfo.get('listen', self.listen)
            charset = hostinfo.get('charset', self.charset)
            server = nginx.Server()
            server.add(nginx.Key('listen', listen),
                       nginx.Key('server_name', hostname),
                       nginx.Key('charset', charset),
                       nginx.Key('autoindex', 'on' if self.autoindex else 'off'))
            self.conf.add(server)
            nginx.dumpf(self.conf, self.root)
            self.server[hostname] = server
        server = self.server[hostname]
        locations = server.filter(btype='Location')
        for l in locations:
            if l.cfile == configfile:
                raise ValueError('config file %s for %s duplicate' % (configfile, hostname))
            if l.value == urlpath:
                raise ValueError('location path %s for %s duplicate' % (urlpath, hostname))
        cf = nginx.Conf()
        location = nginx.Location(urlpath)
        location.add(nginx.Key('alias', rootpath))
        setattr(location, 'cfile', configfile)
        cf.add(location)
        nginx.dumpf(cf, configfile)
        key = nginx.Key('include', configfile)
        server.add(key)
        try:
            nginx.dumpf(self.conf, self.root)
        except Exception:
            server.remove(key)
            os.remove(configfile)
            raise

    def reload(self):
        pass

    def start(self):
        pass

    def stop(self):
        pass


deployer = NginxDeploy()
