from simpleutil.config import cfg
def list_server_opts():
    from simpleservice.ormdb.config import database_opts
    from goperation.manager.wsgi.config import route_opts
    cfg.set_defaults(route_opts, routes=['gopcdn.api.wsgi.routers'])
    return route_opts + database_opts


def list_agent_opts():
    from goperation.manager.rpc.agent.config import rpc_endpoint_opts
    from gopcdn.deploy.config import deploy_opts
    from gopcdn.checkout.config import checkout_opts
    from gopcdn.upload.config import upload_opts
    cfg.set_defaults(rpc_endpoint_opts, module='gopcdn.api.rpc')
    return rpc_endpoint_opts + deploy_opts + checkout_opts + upload_opts
