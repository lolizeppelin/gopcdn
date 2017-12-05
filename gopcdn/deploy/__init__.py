from simpleutil.config import cfg
from simpleutil.utils import importutils
from gopcdn.deploy.config import deploy_opts

CONF = cfg.CONF


def deployer(impl):
    obj = 'gopcdn.deploy.impl._%s.deployer' % impl
    return importutils.import_class(obj)
