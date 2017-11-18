CDN = 'gopcdn'

ENABLE = 1
DISENABLE = 0

ANY = 0
ANDROID = 1
IOS = 2

EntityTypeMap = {IOS: 'ios',
                 ANDROID: 'android',
                 ANY: 'any'}

InvertEntityTypeMap = dict([(v, k) for k, v in EntityTypeMap.iteritems()])

SMALL_PACKAGE = 0
UPDATE_PACKAGE = 1
FULL_PACKAGE = 2

PackageTypeMap = {SMALL_PACKAGE: 'small',
                  UPDATE_PACKAGE: 'update',
                  FULL_PACKAGE: 'full'}

# from itertools import izip
# InvertPackageTypeMap = dict(izip(PackageTypeMap.itervalues(), PackageTypeMap.iterkeys()))
InvertPackageTypeMap = dict([(v, k) for k, v in PackageTypeMap.iteritems()])