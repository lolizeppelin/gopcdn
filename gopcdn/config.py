def list_opts():
    from simpleservice.ormdb.config import database_opts
    from goperation.manager.rpc.agent.config import rpc_endpoint_opts
    from goperation.manager.wsgi.config import route_opts
    from gopcdn.deploy.config import deploy_opts
    from gopcdn.checkout.config import checkout_opts
    return route_opts + rpc_endpoint_opts + deploy_opts + checkout_opts + database_opts
