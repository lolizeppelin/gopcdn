from simpleutil.config import cfg
from simpleservice.ormdb.config import database_opts

CONF = cfg.CONF


def register_opts(group):
    # database for gopcdn
    CONF.register_opts(database_opts, group)


def list_opts():
    from goperation.manager.rpc.agent.config import rpc_endpoint_opts
    from goperation.manager.wsgi.config import route_opts
    return route_opts + rpc_endpoint_opts + database_opts
