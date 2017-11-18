from simpleutil.config import cfg
from simpleutil.utils import importutils
from gopcdn.config import endpoint_group
from gopcdn.checkout.conf import checkout_opts

CONF = cfg.CONF

CONF.register_opts(checkout_opts, endpoint_group)


def checkouter(impl):
    obj = 'gopcdn.checkout.impl._%s.checkouter' % impl
    return importutils.import_class(obj)
