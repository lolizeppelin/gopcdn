from simpleutil.config import cfg
from gopcdn.api.wsgi.config import register_opts

from gopcdn import common

CONF = cfg.CONF

register_opts(CONF.find_group(common.CDN))


