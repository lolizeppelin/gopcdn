from simpleutil.config import cfg
from simpleutil.utils import importutils
from gopcdn.checkout.config import checkout_opts

CONF = cfg.CONF


def checkouter(impl):
    obj = 'gopcdn.checkout.impl._%s.checkouter' % impl
    return importutils.import_class(obj)
