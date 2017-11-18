from simpleutil.config import cfg

from simpleservice.ormdb.config import database_opts

from gopcdn import common

CONF = cfg.CONF

endpoint_group = CONF._get_group(common.CDN, autocreate=False)
# database for gopcdn
CONF.register_opts(database_opts, endpoint_group)