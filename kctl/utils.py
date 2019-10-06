
from pathlib import Path
from hashlib import md5
from yaml import safe_load
from enum import Enum
from box import Box


BOLD = '\033[1m{}\033[0m'


def decorator_group(options):
    """returns a decorator which bundles the given decorators

    :param options: iterable of decorators
    :return: single decorator

    Example:
        deploy_options = option_group([
            click.option('-c', '--connection', required=True),
            click.option('-r', '--rebind', is_flag=True),
            click.option('-d', '--debug', is_flag=True),
        ])

    """
    def option_decorator(f):
        for option in options:
            f = option(f)
        return f
    return option_decorator


class Ktype(Enum):
    BASE = 0
    PIPELINE = 1
    SERVICE = 2


class Yaml(Box):
    """
    Class for managing a yaml as a python object.

    :param path: path to .yaml file
    """
    def __init__(self, path):
        self.__path__ = path
        self.__yaml__ = safe_load(open(path))
        self.__version__ = self.__yaml__.pop('version')

        if 'base' in self.__yaml__:
            self.__type__ = KType.BASE
        elif 'pipeline' in self.__yaml__:
            self.__type__ = KType.PIPELINE
        elif 'service' in self.__yaml__:
            self.__type__ = KType.SERVICE
        else:
            raise ValueError('Invalid yaml type for %s' % self.__path__)

        super().__init__(self.__yaml__)


class AppManager:
    """Manager that keeps track of all of the koursaros
    paths and packages. Passed around at runtime to make
    things more efficient.

    :param base: base path to check for pipeline default=CWD
    """

    def __init__(self, base='.'):
        self.base = Path(base).absolute()
        self.pkg_path = Path(__import__('koursaros').__path__[0])
        self.lookup_path = [self.base, self.root, self.pkg_path]

    @property
    def root(self):
        for path in self.base.parents:
            if path.joinpath('.kapp').is_dir():
                return path

    def search_path(self, name, type):
        for path in self.lookup_path:
            service_path = path.joinpath(type).joinpath(name)
            if service_path.is_dir():
                return service_path

    @staticmethod
    def hash_files(paths):
        return [md5(open(path, 'rb').read()).hexdigest() for path in paths]

    def raise_if_app_root(self):
        if self.root is not None:
            raise IsADirectoryError(f'"{self.base}" is already a pipeline')

    def raise_if_no_app_root(self):
        if self.root is None:
            raise NotADirectoryError(f'"{self.base}" is not a pipeline')