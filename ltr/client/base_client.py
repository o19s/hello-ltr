from abc import ABC, abstractmethod

'''
    This project demonstrates working with LTR in Elasticsearch and Solr

    The goal of this class is to abstract away the server and highlight the steps
    required to begin working with LTR.  This keeps the examples agnostic about
    which backend is being used, but the implementations of each client
    should be useful references to those getting started with LTR on
    their specific platform
'''
class BaseClient(ABC):

    @abstractmethod
    def delete_index(self, index):
        pass

    @abstractmethod
    def create_index(self, index, settings):
        pass

    @abstractmethod
    def index_documents(self, index, dictionary):
        pass

    @abstractmethod
    def reset_ltr(self):
        pass

    @abstractmethod
    def create_featureset(self, index, name, config):
        pass

    @abstractmethod
    def log_query(self, index, featureset, query):
        pass

    @abstractmethod
    def submit_model(self, featureset, model_name, model_payload):
        pass

    @abstractmethod
    def model_query(self, index, model, model_params, query):
        pass

