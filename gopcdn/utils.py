from simpleutil.common.exceptions import InvalidArgument

from gopcdn import common

def validate_etype(etype):
    if isinstance(etype, basestring):
        if etype.isdigit():
            etype = int(etype)
        else:
            etype = common.InvertEntityTypeMap.get(etype)
    if etype not in common.EntityTypeMap:
        raise InvalidArgument('Entity type %s error, can not find in EntityTypeMap' % str(etype))
    return etype