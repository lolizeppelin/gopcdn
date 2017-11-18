from simpleutil.config import cfg
from simpleutil.utils import importutils
from gopcdn.config import endpoint_group
from gopcdn.deploy.conf import deploy_opts

CONF = cfg.CONF

CONF.register_opts(deploy_opts, endpoint_group)

obj = 'gopcdn.deploy.impl._%s.deployer' % CONF[endpoint_group.name].deployer
deployer = importutils.import_class(obj)
