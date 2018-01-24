from simpleutil.utils import argutils
from simpleservice.plugin.exceptions import ServerExecuteRequestError

from goperation.api.client import GopHttpClientApi
from goperation.manager import common

from gopcdn.common import CDN


class GopCdnClient(GopHttpClientApi):

    deploer_ports_path = '/gopcdn/agent/%s'

    cdndomain_search_path = '/gopcdn/domain'
    cdndomains_list_path = '/gopcdn/entitys'

    cdndomains_path = '/gopcdn/cdndomains'
    cdndomain_path = '/gopcdn/cdndomains/%s'
    cdndomain_path_ex_path = '/gopcdn/cdndomains/%s/%s'

    cdnresources_path = '/gopcdn/cdnresources'
    cdnresource_path = '/gopcdn/cdnresources/%s'
    cdnresources_ex_path = '/gopcdn/cdnresources/%s/%s'

    resversion_quotes_path = '/gopcdn/resversion/quotes'
    resversion_quote_path = '/gopcdn/resversion/quotes/%s'

    def __init__(self, httpclient):
        self.endpoint = CDN
        super(GopCdnClient, self).__init__(httpclient)

    def show_deploer_ports(self, agent_id):
        resp, results = self.get(action=self.deploer_ports_path % str(agent_id), body=None)
        if results['resultcode'] != common.RESULT_SUCCESS:
            raise ServerExecuteRequestError(message='show cdn domian deploer ports fail:%d' % results['resultcode'],
                                            code=resp.status_code,
                                            resone=results['result'])
        return results

    # ---------------cdndomain api--------------------
    def cdndomain_search(self, domain):
        body = dict(domain=domain)
        resp, results = self.get(action=self.cdndomain_search_path, body=body)
        if results['resultcode'] != common.RESULT_SUCCESS:
            raise ServerExecuteRequestError(message='search cdn domain fail:%d' % results['resultcode'],
                                            code=resp.status_code,
                                            resone=results['result'])
        return results

    def cdndomains_shows(self, entitys):
        body = dict(entitys=argutils.map_to_int(entitys))
        resp, results = self.get(action=self.cdndomains_list_path, body=body)
        if results['resultcode'] != common.RESULT_SUCCESS:
            raise ServerExecuteRequestError(message='list cdn domain fail:%d' % results['resultcode'],
                                            code=resp.status_code,
                                            resone=results['result'])
        return results

    def cdndomain_create(self, body):
        resp, results = self.post(action=self.cdndomains_path, body=body)
        if results['resultcode'] != common.RESULT_SUCCESS:
            raise ServerExecuteRequestError(message='create cdn domain fail:%d' % results['resultcode'],
                                            code=resp.status_code,
                                            resone=results['result'])
        return results

    def cdndomain_index(self, body=None):
        resp, results = self.get(action=self.cdndomains_path, body=body)
        if results['resultcode'] != common.RESULT_SUCCESS:
            raise ServerExecuteRequestError(message='index cdn domain fail:%d' % results['resultcode'],
                                            code=resp.status_code,
                                            resone=results['result'])
        return results

    def cdndomain_show(self, entity, body=None):
        resp, results = self.get(action=self.cdndomain_path % (str(entity)), body=body)
        if results['resultcode'] != common.RESULT_SUCCESS:
            raise ServerExecuteRequestError(message='show cdn domain fail:%d' % results['resultcode'],
                                            code=resp.status_code,
                                            resone=results['result'])
        return results

    def cdndomain_delete(self, entity, body=None):
        resp, results = self.delete(action=self.cdndomain_path % (str(entity)), body=body)
        if results['resultcode'] != common.RESULT_SUCCESS:
            raise ServerExecuteRequestError(message='delete cdn domain fail:%d' % results['resultcode'],
                                            code=resp.status_code,
                                            resone=results['result'])
        return results

    def cdndomain_add(self, entity, domains):
        body = dict(domains=argutils.map_with(domains, str))
        resp, results = self.post(action=self.cdndomain_path_ex_path % (str(entity), 'domains'), body=body)
        if results['resultcode'] != common.RESULT_SUCCESS:
            raise ServerExecuteRequestError(message='add cdn domain name fail:%d' % results['resultcode'],
                                            code=resp.status_code,
                                            resone=results['result'])
        return results

    def cdndomain_remove(self, entity, domains):
        body = dict(domains=argutils.map_with(domains, str))
        resp, results = self.delete(action=self.cdndomain_path_ex_path % (str(entity), 'domains'), body=body)
        if results['resultcode'] != common.RESULT_SUCCESS:
            raise ServerExecuteRequestError(message='remove cdn domain name fail:%d' % results['resultcode'],
                                            code=resp.status_code,
                                            resone=results['result'])
        return results

    # ---------------cdnresource api--------------------
    def cdnresource_create(self, body):
        resp, results = self.post(action=self.cdnresources_path, body=body)
        if results['resultcode'] != common.RESULT_SUCCESS:
            raise ServerExecuteRequestError(message='create cdn resource fail:%d' % results['resultcode'],
                                            code=resp.status_code,
                                            resone=results['result'])
        return results

    def cdnresource_index(self, body=None):
        resp, results = self.get(action=self.cdnresources_path, body=body)
        if results['resultcode'] != common.RESULT_SUCCESS:
            raise ServerExecuteRequestError(message='list cdn resource fail:%d' % results['resultcode'],
                                            code=resp.status_code,
                                            resone=results['result'])
        return results

    def cdnresource_show(self, resource_id, body=None):
        resp, results = self.get(action=self.cdnresource_path % str(resource_id), body=body)
        if results['resultcode'] != common.RESULT_SUCCESS:
            raise ServerExecuteRequestError(message='show cdn resource fail:%d' % results['resultcode'],
                                            code=resp.status_code,
                                            resone=results['result'])
        return results

    def cdnresource_update(self, resource_id, body):
        resp, results = self.put(action=self.cdnresource_path % str(resource_id), body=body)
        if results['resultcode'] != common.RESULT_SUCCESS:
            raise ServerExecuteRequestError(message='update cdn resource fail:%d' % results['resultcode'],
                                            code=resp.status_code,
                                            resone=results['result'])
        return results

    def cdnresource_delete(self, resource_id):
        resp, results = self.delete(action=self.cdnresource_path % str(resource_id))
        if results['resultcode'] != common.RESULT_SUCCESS:
            raise ServerExecuteRequestError(message='delete cdn resource fail:%d' % results['resultcode'],
                                            code=resp.status_code,
                                            resone=results['result'])
        return results

    def cdnresource_shows(self, resource_id, body=None):
        resp, results = self.get(action=self.cdnresources_ex_path % (str(resource_id), 'shows'),
                                  body=body)
        if results['resultcode'] != common.RESULT_SUCCESS:
            raise ServerExecuteRequestError(message='show cdn resources fail:%d' % results['resultcode'],
                                            code=resp.status_code,
                                            resone=results['result'])
        return results

    def cdnresource_reset(self, resource_id, body):
        resp, results = self.post(action=self.cdnresources_ex_path % (str(resource_id), 'reset'),
                                  body=body)
        if results['resultcode'] != common.RESULT_SUCCESS:
            raise ServerExecuteRequestError(message='reset cdn resource log fail:%d' % results['resultcode'],
                                            code=resp.status_code,
                                            resone=results['result'])
        return results

    def cdnresource_upgrade(self, resource_id, body):
        resp, results = self.post(action=self.cdnresources_ex_path % (str(resource_id), 'upgrade'),
                                  body=body)
        if results['resultcode'] != common.RESULT_SUCCESS:
            raise ServerExecuteRequestError(message='upgrade cdn resource log fail:%d' % results['resultcode'],
                                            code=resp.status_code,
                                            resone=results['result'])
        return results

    def cdnresource_getlog(self, resource_id, body):
        resp, results = self.get(action=self.cdnresources_ex_path % (str(resource_id), 'log'),
                                 body=body)
        if results['resultcode'] != common.RESULT_SUCCESS:
            raise ServerExecuteRequestError(message='get cdn resource log fail:%d' % results['resultcode'],
                                            code=resp.status_code,
                                            resone=results['result'])
        return results

    def cdnresource_postlog(self, resource_id, body):
        resp, results = self.retryable_post(action=self.cdnresources_ex_path % (str(resource_id), 'log'),
                                            body=body)
        if results['resultcode'] != common.RESULT_SUCCESS:
            raise ServerExecuteRequestError(message='get cdn resource log fail:%d' % results['resultcode'],
                                            code=resp.status_code,
                                            resone=results['result'])
        return results

    def cdnresource_add_file(self, resource_id, body):
        resp, results = self.retryable_post(action=self.cdnresources_ex_path % (str(resource_id), 'file'),
                                            body=body)
        if results['resultcode'] != common.RESULT_SUCCESS:
            raise ServerExecuteRequestError(message='add file to cdn resource fail:%d' % results['resultcode'],
                                            code=resp.status_code,
                                            resone=results['result'])
        return results

    def cdnresource_delete_file(self, resource_id, body):
        resp, results = self.delete(action=self.cdnresources_ex_path % (str(resource_id), 'file'),
                                    body=body)
        if results['resultcode'] != common.RESULT_SUCCESS:
            raise ServerExecuteRequestError(message='delete file from cdn resource fail:%d' % results['resultcode'],
                                            code=resp.status_code,
                                            resone=results['result'])
        return results

    def cdnresource_list_file(self, resource_id, body):
        resp, results = self.get(action=self.cdnresources_ex_path % (str(resource_id), 'file'),
                                 body=body)
        if results['resultcode'] != common.RESULT_SUCCESS:
            raise ServerExecuteRequestError(message='delete file from cdn resource fail:%d' % results['resultcode'],
                                            code=resp.status_code,
                                            resone=results['result'])
        return results

    def cdnresource_getremark(self, resource_id, body):
        resp, results = self.get(action=self.cdnresources_ex_path % (str(resource_id), 'remark'),
                                 body=body)
        if results['resultcode'] != common.RESULT_SUCCESS:
            raise ServerExecuteRequestError(message='get cdn resource remarks fail:%d' % results['resultcode'],
                                            code=resp.status_code,
                                            resone=results['result'])
        return results

    def cdnresource_addremark(self, resource_id, body):
        resp, results = self.post(action=self.cdnresources_ex_path % (str(resource_id), 'remark'),
                                  body=body)
        if results['resultcode'] != common.RESULT_SUCCESS:
            raise ServerExecuteRequestError(message='add cdn resource remark fail:%d' % results['resultcode'],
                                            code=resp.status_code,
                                            resone=results['result'])
        return results

    def cdnresource_delremark(self, resource_id, body):
        resp, results = self.delete(action=self.cdnresources_ex_path % (str(resource_id), 'remark'),
                                    body=body)
        if results['resultcode'] != common.RESULT_SUCCESS:
            raise ServerExecuteRequestError(message='delete cdn resource remark fail:%d' % results['resultcode'],
                                            code=resp.status_code,
                                            resone=results['result'])
        return results

    def cdnresource_getversion(self, resource_id, body):
        resp, results = self.get(action=self.cdnresources_ex_path % (str(resource_id), 'version'),
                                 body=body)
        if results['resultcode'] != common.RESULT_SUCCESS:
            raise ServerExecuteRequestError(message='get cdn resource version fail:%d' % results['resultcode'],
                                            code=resp.status_code,
                                            resone=results['result'])
        return results

    def cdnresource_addversion(self, resource_id, body):
        resp, results = self.post(action=self.cdnresources_ex_path % (str(resource_id), 'version'),
                                  body=body)
        if results['resultcode'] != common.RESULT_SUCCESS:
            raise ServerExecuteRequestError(message='add cdn resource version fail:%d' % results['resultcode'],
                                            code=resp.status_code,
                                            resone=results['result'])
        return results

    def cdnresource_delversion(self, resource_id, body):
        resp, results = self.delete(action=self.cdnresources_ex_path % (str(resource_id), 'version'),
                                    body=body)
        if results['resultcode'] != common.RESULT_SUCCESS:
            raise ServerExecuteRequestError(message='delete cdn resource version fail:%d' % results['resultcode'],
                                            code=resp.status_code,
                                            resone=results['result'])
        return results

    def cdnresource_add_base_quote(self, resource_id):
        resp, results = self.post(action=self.cdnresources_ex_path % (str(resource_id), 'quote'))
        if results['resultcode'] != common.RESULT_SUCCESS:
            raise ServerExecuteRequestError(message='add cdn resource one base quote fail:%d' % results['resultcode'],
                                            code=resp.status_code,
                                            resone=results['result'])
        return results

    def cdnresource_remove_base_quote(self, resource_id):
        resp, results = self.delete(action=self.cdnresources_ex_path % (str(resource_id), 'quote'))
        if results['resultcode'] != common.RESULT_SUCCESS:
            raise ServerExecuteRequestError(message='remove cdn resource one base quote fail:%d' %
                                                    results['resultcode'],
                                            code=resp.status_code,
                                            resone=results['result'])
        return results

    # ---------------cdnresource quote api--------------------
    def create_resversions_quote(self, version_id):
        resp, results = self.retryable_post(action=self.resversion_quotes_path,
                                            body=dict(version_id=version_id))
        if results['resultcode'] != common.RESULT_SUCCESS:
            raise ServerExecuteRequestError(message='create cdn resource quote fail:%d' % results['resultcode'],
                                            code=resp.status_code,
                                            resone=results['result'])
        return results

    def delete_resversions_quote(self, quote_id, body):
        resp, results = self.delete(action=self.resversion_quote_path % str(quote_id),
                                            body=body)
        if results['resultcode'] != common.RESULT_SUCCESS:
            raise ServerExecuteRequestError(message='delete cdn resource quote fail:%d' % results['resultcode'],
                                            code=resp.status_code,
                                            resone=results['result'])
        return results

    def update_resversions_quote(self, quote_id, version):
        resp, results = self.delete(action=self.resversion_quote_path % str(quote_id),
                                    body=dict(version=version))
        if results['resultcode'] != common.RESULT_SUCCESS:
            raise ServerExecuteRequestError(message='delete cdn resource quote fail:%d' % results['resultcode'],
                                            code=resp.status_code,
                                            resone=results['result'])
        return results

    def show_resversions_quote(self, quote_id, body):
        resp, results = self.delete(action=self.resversion_quote_path % str(quote_id),
                                    body=body)
        if results['resultcode'] != common.RESULT_SUCCESS:
            raise ServerExecuteRequestError(message='delete cdn resource quote fail:%d' % results['resultcode'],
                                            code=resp.status_code,
                                            resone=results['result'])
        return results
