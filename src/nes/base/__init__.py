import pickle
from functools import wraps
from typing import TypeVar

import ruamel.yaml.constructor
from ruamel.yaml import YAML

from ..helper import set_logger, time_profile, MemoryCache

_tb = TypeVar('T', bound='TrainableBase')
yaml = YAML()


class TrainableBase:
    _timeit = time_profile

    def __init__(self, *args, **kwargs):
        self.is_trained = False
        self.verbose = 'verbose' in kwargs and kwargs['verbose']
        self.logger = set_logger(self.__class__.__name__, self.verbose)
        self.memcached = MemoryCache(cache_path='.nes_cache')
        self._yaml_kwargs = {}

    def __getstate__(self):
        d = dict(self.__dict__)
        del d['logger']
        del d['memcached']
        return d

    def __setstate__(self, d):
        self.__dict__.update(d)
        self.logger = set_logger(self.__class__.__name__, self.verbose)
        self.memcached = MemoryCache(cache_path='.nes_cache')

    @staticmethod
    def _train_required(func):
        @wraps(func)
        def arg_wrapper(self, *args, **kwargs):
            if self.is_trained:
                return func(self, *args, **kwargs)
            else:
                raise RuntimeError('training is required before calling "%s"' % func.__name__)

        return arg_wrapper

    @staticmethod
    def _as_train_func(func):
        @wraps(func)
        def arg_wrapper(self, *args, **kwargs):
            if self.is_trained:
                self.logger.warning('"%s" has been trained already, '
                                    'training it again will override the previous training' % self.__class__.__name__)
            f = func(self, *args, **kwargs)
            self.is_trained = True
            return f

        return arg_wrapper

    @staticmethod
    def _yaml_init(func):
        @wraps(func)
        def arg_wrapper(self, *args, **kwargs):
            _kwargs = locals()
            _kwargs.pop('self')
            _kwargs.pop('func')
            f = func(self, *args, **kwargs)
            self._yaml_kwargs = _kwargs
            return f

        return arg_wrapper

    def train(self, *args, **kwargs):
        raise NotImplementedError

    @_timeit
    def dump(self, filename: str) -> None:
        with open(filename, 'wb') as fp:
            pickle.dump(self, fp)

    @_timeit
    def dump_yaml(self, filename: str) -> None:
        yaml = YAML(typ='unsafe')
        yaml.register_class(self.__class__)
        with open(filename, 'w') as fp:
            yaml.dump(self, fp)

    @classmethod
    @_timeit
    def load_yaml(cls, filename: str) -> _tb:
        yaml = YAML(typ='unsafe')
        yaml.register_class(cls)
        with open(filename) as fp:
            return yaml.load(fp)

    @staticmethod
    @_timeit
    def load(filename: str) -> _tb:
        with open(filename, 'rb') as fp:
            return pickle.load(fp)

    def close(self):
        pass

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        self.close()

    @classmethod
    def to_yaml(cls, representer, data):
        return representer.represent_mapping('!' + cls.__name__, data._yaml_kwargs)

    @classmethod
    def from_yaml(cls, constructor, node):
        data = ruamel.yaml.constructor.SafeConstructor.construct_mapping(
            constructor, node, deep=True)
        if 'args' in data and 'kwargs' in data:
            return cls(*data['args'], **data['kwargs'])
        elif 'args' not in data and 'kwargs' in data:
            return cls(**data['kwargs'])
        elif 'args' in data and 'kwargs' not in data:
            return cls(*data['args'])
        else:
            return cls(**data)
