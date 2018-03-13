from gopcdn.plugin.deploy.config import deploy_opts
from simpleutil.config import cfg
from simpleutil.utils import importutils

CONF = cfg.CONF


def deployer(impl):
    obj = 'gopcdn.plugin.deploy.impl._%s.deployer' % impl
    return importutils.import_class(obj)
