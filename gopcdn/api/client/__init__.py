from simpleservice.plugin.exceptions import ServerExecuteRequestError

from goperation.api.client import GopHttpClientApi
from goperation.manager import common

from gopcdn.common import CDN


class GopCdnClient(GopHttpClientApi):

    cdnresources_path = '/gopcdn/%s/cdnresources'
    cdnresource_path = '/gopcdn/%s/cdnresources/%s'
    cdnresources_ex_path = '/gopcdn/%s/cdnresources/%s/%s'

    packages_path = '/gopcdn/%s/packages'
    package_path = '/gopcdn/%s/packages/%s'
    packages_ex_path = '/gopcdn/%s/packages/%s/%s'

    def __init__(self, httpclient):
        self.endpoint = CDN
        super(GopCdnClient, self).__init__(httpclient)

    def cdnresource_create(self, endpoint, body):
        resp, results = self.post(action=self.cdnresources_path % endpoint, body=body)
        if results['resultcode'] != common.RESULT_SUCCESS:
            raise ServerExecuteRequestError(message='create %s cdn resource fail:%d' %
                                                    (endpoint, results['resultcode']),
                                            code=resp.status_code,
                                            resone=results['result'])
        return results

    def cdnresource_index(self, endpoint, body):
        resp, results = self.get(action=self.cdnresources_path % endpoint, body=body)
        if results['resultcode'] != common.RESULT_SUCCESS:
            raise ServerExecuteRequestError(message='list %s cdn resource fail:%d' %
                                                    (endpoint, results['resultcode']),
                                            code=resp.status_code,
                                            resone=results['result'])
        return results

    def cdnresource_show(self, endpoint, entity, body):
        resp, results = self.get(action=self.cdnresource_path % (endpoint, str(entity)), body=body)
        if results['resultcode'] != common.RESULT_SUCCESS:
            raise ServerExecuteRequestError(message='show cdn resource fail:%d' % results['resultcode'],
                                            code=resp.status_code,
                                            resone=results['result'])
        return results

    def cdnresource_update(self, endpoint, entity, body):
        resp, results = self.put(action=self.cdnresource_path % (endpoint, str(entity)), body=body)
        if results['resultcode'] != common.RESULT_SUCCESS:
            raise ServerExecuteRequestError(message='update cdn resource fail:%d' % results['resultcode'],
                                            code=resp.status_code,
                                            resone=results['result'])
        return results

    def cdnresource_delete(self, endpoint, entity, body):
        resp, results = self.delete(action=self.cdnresource_path % (endpoint, str(entity)), body=body)
        if results['resultcode'] != common.RESULT_SUCCESS:
            raise ServerExecuteRequestError(message='delete cdn resource fail:%d' % results['resultcode'],
                                            code=resp.status_code,
                                            resone=results['result'])
        return results

    def cdnresource_checkout(self, endpoint, entity, body):
        resp, results = self.delete(action=self.cdnresource_path % (endpoint, str(entity)), body=body)
        if results['resultcode'] != common.RESULT_SUCCESS:
            raise ServerExecuteRequestError(message='checkout cdn resource fail:%d' % results['resultcode'],
                                            code=resp.status_code,
                                            resone=results['result'])
        return results

    def cdnresource_getlog(self, endpoint, entity, body):
        resp, results = self.get(action=self.cdnresources_ex_path % (endpoint, str(entity), 'log'),
                                 body=body)
        if results['resultcode'] != common.RESULT_SUCCESS:
            raise ServerExecuteRequestError(message='get cdn resource log fail:%d' % results['resultcode'],
                                            code=resp.status_code,
                                            resone=results['result'])
        return results

    def cdnresource_postlog(self, endpoint, entity, body):
        resp, results = self.retryable_post(action=self.cdnresources_ex_path % (endpoint, str(entity), 'log'),
                                            body=body)
        if results['resultcode'] != common.RESULT_SUCCESS:
            raise ServerExecuteRequestError(message='get cdn resource log fail:%d' % results['resultcode'],
                                            code=resp.status_code,
                                            resone=results['result'])
        return results

    def package_create(self, endpoint, body):
        resp, results = self.post(action=self.packages_path % endpoint, body=body)
        if results['resultcode'] != common.RESULT_SUCCESS:
            raise ServerExecuteRequestError(message='create %s package fail:%d' %
                                                    (endpoint, results['resultcode']),
                                            code=resp.status_code,
                                            resone=results['result'])
        return results

    def package_index(self, endpoint, body):
        resp, results = self.get(action=self.packages_path % endpoint, body=body)
        if results['resultcode'] != common.RESULT_SUCCESS:
            raise ServerExecuteRequestError(message='list %s package fail:%d' %
                                                    (endpoint, results['resultcode']),
                                            code=resp.status_code,
                                            resone=results['result'])
        return results

    def package_show(self, endpoint, package_id, body):
        resp, results = self.get(action=self.package_path % (endpoint, package_id), body=body)
        if results['resultcode'] != common.RESULT_SUCCESS:
            raise ServerExecuteRequestError(message='show %s package fail:%d' %
                                                    (endpoint, results['resultcode']),
                                            code=resp.status_code,
                                            resone=results['result'])
        return results

    def package_update(self, endpoint, package_id, body):
        resp, results = self.put(action=self.package_path % (endpoint, package_id), body=body)
        if results['resultcode'] != common.RESULT_SUCCESS:
            raise ServerExecuteRequestError(message='update %s package fail:%d' %
                                                    (endpoint, results['resultcode']),
                                            code=resp.status_code,
                                            resone=results['result'])
        return results

    def package_delete(self, endpoint, package_id, body):
        resp, results = self.delete(action=self.package_path % (endpoint, package_id), body=body)
        if results['resultcode'] != common.RESULT_SUCCESS:
            raise ServerExecuteRequestError(message='delete %s package fail:%d' %
                                                    (endpoint, results['resultcode']),
                                            code=resp.status_code,
                                            resone=results['result'])
        return results

    def package_source_add(self, endpoint, package_id, body):
        resp, results = self.retryable_post(action=self.package_path % (endpoint, package_id, 'source'),
                                            body=body)
        if results['resultcode'] != common.RESULT_SUCCESS:
            raise ServerExecuteRequestError(message='add %s package source fail:%d' %
                                                    (endpoint, results['resultcode']),
                                            code=resp.status_code,
                                            resone=results['result'])
        return results

    def package_source_delete(self, endpoint, package_id, body):
        resp, results = self.delete(action=self.package_path % (endpoint, package_id, 'source'),
                                    body=body)
        if results['resultcode'] != common.RESULT_SUCCESS:
            raise ServerExecuteRequestError(message='delete %s package source fail:%d' %
                                                    (endpoint, results['resultcode']),
                                            code=resp.status_code,
                                            resone=results['result'])
        return results

    def package_source_update(self, endpoint, package_id, body):
        resp, results = self.put(action=self.package_path % (endpoint, package_id, 'source'),
                                 body=body)
        if results['resultcode'] != common.RESULT_SUCCESS:
            raise ServerExecuteRequestError(message='update %s package source fail:%d' %
                                                    (endpoint, results['resultcode']),
                                            code=resp.status_code,
                                            resone=results['result'])
        return results

    def package_change_group(self, endpoint, package_id, body):
        resp, results = self.put(action=self.package_path % (endpoint, package_id, 'group'),
                                 body=body)
        if results['resultcode'] != common.RESULT_SUCCESS:
            raise ServerExecuteRequestError(message='update %s package group fail:%d' %
                                                    (endpoint, results['resultcode']),
                                            code=resp.status_code,
                                            resone=results['result'])
        return results
