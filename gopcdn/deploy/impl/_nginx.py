# -*- coding:utf-8 -*-
import os
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
        self.pid = None

    def _server_conf(self, entity):
        return os.path.join(self.configdir, 'gopcdn-%d.conf' % entity)

    def init_conf(self, maps):
        for entity in maps:
            if entity in self.server:
                raise RuntimeError('Entity %d duplicate' % entity)
            cfile = self._server_conf(entity)
            if not os.path.exists(cfile):
                domain = maps[entity]
                self.deploy_domian(entity, listen=domain.get('listen'),
                                   port=domain.get('port'), charset=domain.get('character_set'),
                                   domains=domain.get('domains'))
                resources = domain.get('resources')
                for resource in resources:
                    urlpath = resource.get('urlpath')
                    rootpath = resource.get('rootpath')
                    self.deploy_resource(entity, urlpath=urlpath, rootpath=rootpath,
                                         configfile=domain.get('configfile'))
            else:
                conf = nginx.loadf(cfile)
                if len(conf.servers) > 1:
                    raise RuntimeError('Entity %d config file server more then one')
                server =  conf.servers[0]
                if server.locations:
                    raise RuntimeError('locations in server config file')
                self.server.setdefault(entity, server)
                for key in server.keys:
                    if key.name == 'include':
                        configfile = key.value
                        # Location 配置文件存在
                        if os.path.exists(configfile):
                            cf = nginx.loadf(configfile)
                            if cf.server:
                                raise RuntimeError('location config file get server config')
                            # 配置文件对象设置配置文件路径属性
                            setattr(cf, 'cfile', configfile)
                            # 绑定location配置文件对象
                            setattr(server, 'alias', cf)
                        # 配置文件不存在
                        else:
                            resources = domain.get('resources')
                            configfile = domain.get('configfile')
                            for resource in resources:
                                urlpath = resource.get('urlpath')
                                rootpath = resource.get('rootpath')
                                self.deploy_resource(entity, urlpath=urlpath,
                                                     rootpath=rootpath,
                                                     configfile=configfile)
                    break

    def find_nginx(self):
        if self.pid:
            try:
                p = psutil.Process(pid=self.pid)
                if p.name() != 'nginx' or p.username() != 'root':
                    self.pid = None
            except psutil.NoSuchProcess:
                self.pid = None
        if self.pid:
            return
        for proc in psutil.process_iter(attrs=['pid', 'name', 'username']):
            if proc.info.get('name') == 'nginx' and proc.info.get('username') == 'root':
                self.pid = proc.info.get('pid')
                break

    def deploy_domian(self, entity, listen, port, charset, domains):
        if port not in self.ports:
            raise DeployError('Entity %d port not allowed' % entity)
        cfile = self._server_conf(entity)
        if entity in self.server:
            raise DeployError('Entity %d duplicate' % entity)
        conf = nginx.Conf()
        server = nginx.Server()
        conf.add(server)

        domains = ' '.join(domains) if domains else '_'
        if listen:
            listen = '%s:%d' % (listen, port)
        else:
            listen = '%d' % port

        server.add(nginx.Key('listen', listen),
                   nginx.Key('server_name', domains),
                   nginx.Key('charset', charset or self.character_set),
                   nginx.Key('autoindex', 'on' if self.autoindex else 'off'))
        self.server.setdefault(entity, server)
        nginx.dumpf(conf, cfile)

    def undeploy_domian(self, entity):
        cfile = self._server_conf(entity)
        if entity not in self.server:
            if os.path.exists(cfile):
                os.remove(cfile)
            return
        server = self.server[entity]
        cf = server.alias
        locations = cf.filter(btype='Location')
        if locations:
            raise DeployError('Reference by location, undeploy domain entity %d fail' % entity)
        self.server.pop(entity)
        if os.path.exists(cfile):
            os.remove(cfile)
        if os.path.exists(cf.cfile):
            os.remove(cf.cfile)

    def deploy_resource(self, entity, urlpath, rootpath, configfile):
        if rootpath == '/':
            raise ValueError('web path is root')
        if not urlpath.startswith('/'):
            urlpath = '/' + urlpath
        if '..' in urlpath or urlpath == '/':
            raise ValueError('urlpath %s error' % urlpath)
        cfile = self._server_conf(entity)
        if entity not in self.server:
            if os.path.exists(cfile):
                os.remove(cfile)
            raise DeployError('Domain entity not in server dict')

        server = self.server[entity]
        # location配置文件丢失,生成配置文件
        if hasattr(server, 'alias') and not os.path.exists(configfile):
            nginx.dumpf(server.alias, configfile)
        # 不存在alias, 添加include字段以及alias属性
        if not hasattr(server, 'alias'):
            conf = nginx.Conf()
            key = nginx.Key('include', configfile)
            server.add(key)
            conf.add(server)
            nginx.dumpf(conf, cfile)
            if os.path.exists(configfile):
                cf = nginx.loadf(configfile)
            else:
                cf = nginx.Conf()
            setattr(cf, 'cfile', configfile)
            setattr(server, 'alias', cf)

        locations = server.alias.filter(btype='Location')
        for location in locations:
            if location.value == urlpath:
                same = False
                for key in location.keys:
                    if key.name == 'alias' and key.value == rootpath:
                        same = True
                        break
                if not same:
                    raise DeployError('location path %s for %s duplicate' % (urlpath, entity))

        location = nginx.Location(urlpath)
        location.add(nginx.Key('alias', rootpath))
        server.alias.add(location)
        nginx.dumpf(server.alias, configfile)

    def undeploy_resource(self, entity, urlpath):
        if not urlpath.startswith('/'):
            urlpath = '/' + urlpath
        server = self.server[entity]
        cf = server.alias
        locations = cf.filter(btype='Location')
        for location in locations:
            if location.value == urlpath:
                locations.remove(location)
                nginx.dumpf(cf, cf.cfile)
                break

    def add_hostnames(self, entity, domains):
        cfile = self._server_conf(entity)
        server = self.server[entity]
        key = server.filter(name='server_name')
        if key.value == '_':
            key.value = ' '.join(domains)
        else:
            hostnames = strutils.Split(key.value)
            hostnames.extend(domains)
            key.value = ' '.join(list(set(hostnames)))
        nginx.dumpf(server, cfile)

    def remove_hostnames(self, entity, domains):
        cfile = self._server_conf(entity)
        server = self.server[entity]
        key = server.filter(name='server_name')
        if key.value == '_':
            return
        else:
            hostnames = set(strutils.Split(key.value))
            hostnames = hostnames - set(domains)
            if not hostnames:
                key.value = '_'
            else:
                key.value = ' '.join(list(hostnames))
        nginx.dumpf(server, cfile)

    def clean(self, entity):
        cfile = self._server_conf(entity)
        self.server.pop(entity, None)
        if os.path.exists(cfile):
            os.remove(cfile)


    def reload(self, raiser=None):
        if systemutils.LINUX:
            self.find_nginx()
            if not self.pid:
                raise DeployError('nginx process not exist')
            os.kill(self.pid, signal.SIGHUP)

    def start(self):
        pass

    def stop(self):
        pass


deployer = NginxDeploy()


if systemutils.LINUX:
    deployer.find_nginx()
