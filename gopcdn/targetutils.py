from simpleutil.config import cfg

from simpleservice.rpc.target import Target

from goperation.manager.common import AGENT
from goperation.manager.config import manager_group

from gopcdn.config import endpoint_group

CONF = cfg.CONF

prefix = CONF[manager_group.name].redis_key_prefix

def target_all(fanout=False):
    return Target(topic='%s.*' % AGENT, fanout=AGENT if fanout else None,
                  namespace=endpoint_group.name)


def target_alltype(agent_type):
    return Target(topic='%s.%s.*' % (AGENT, agent_type),
                  namespace=manager_group.name)


def target_anyone(agent_type):
    return Target(topic='%s.%s' % (AGENT, agent_type),
                  namespace=manager_group.name)


def target_server(agent_type, host, fanout=False):
    return Target(topic='%s.%s' % (AGENT, agent_type),
                  server=host, fanout=AGENT if fanout else None,
                  namespace=manager_group.name)


def target_agent(agent):
    return target_server(agent.agent_type, agent.host)


def target_endpoint(endpoint):
    return Target(fanout=endpoint, server=CONF.host)
