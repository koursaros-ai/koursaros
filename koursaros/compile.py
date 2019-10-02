from koursaros.utils import find_pipe_path, parse_stub_string
from inspect import getsource
from grpc_tools import protoc
import yaml as pyyaml
import os

INVALID_PREFIXES = ('_', '.')
IMPORTS = ['from .messages_pb2 import *', 'from koursaros.base import *']
PROTECTED = ['from']


class CompiledClass:
    __slots__ = ['lines']

    def __init__(self, name, vars_, parent=None):
        parent = f'({parent})' if parent else ''
        lines = []

        for k, v in vars_.items():

            if k in PROTECTED:
                raise ValueError(f'Invalid Attribute Name: "{k}"')

            if isinstance(v, (list, dict, int, self.PlainString)) or v is None:
                lines.append(f'{k} = {v}')

            elif isinstance(v, str):
                lines.append(f'{k} = "{v}"')

            elif callable(v):
                lines += getsource(v).split('\n')

            elif isinstance(v, CompiledClass):
                lines += v.lines

            else:
                raise NotImplementedError(f'var "{k}" of type {type(v)} not implemented')

        self.lines = lines
        self.indent()
        self.lines = [f'class {name}{parent}:'] + self.lines

    def indent(self):
        self.lines = ['    ' + line for line in self.lines]

    def join(self):
        return '\n'.join(self.lines)

    class PlainString(str):
        pass


def set_imports(out_path):
    imports = ''
    for pipeline in next(os.walk(out_path))[1]:
        if not pipeline.startswith(INVALID_PREFIXES):
            imports += f'from .{pipeline} import {pipeline}\n'

    with open(f'{out_path}/__init__.py', 'w') as fh:
        fh.write(imports)


def compile_pipeline(pipe_path, save_path):
    pipeline = dict()
    name = pipe_path.split('/')[-2]
    print(f'Compiling pipeline "{name}"...')
    pipeline['Connections'] = compile_connections(pipe_path)
    pipeline['Services'] = compile_services(pipe_path)

    pipeline = CompiledClass(name, pipeline, parent='Pipeline')

    out_path = f'{save_path}/{name}'
    os.makedirs(out_path, exist_ok=True)
    compile_messages(pipe_path, out_path)
    out_file = f'{out_path}/__init__.py'

    print(f'Writing to {out_file}...')
    with open(out_file, 'w') as fh:
        fh.write('\n'.join(IMPORTS) + '\n\n' + pipeline.join())

    set_imports(save_path)


def compile_messages(pipe_path, out_path):
    print(f'Compiling messages for {pipe_path}')

    protoc.main((
        '',
        f'-I={pipe_path}',
        f'--python_out={out_path}',
        f'{pipe_path}/messages.proto',
    ))


def compile_connections(path):
    connections = dict()
    path = find_pipe_path(path) + '/connections.yaml'
    connections['path'] = path
    yaml = pyyaml.safe_load(open(path))
    connections['yaml'] = yaml

    connections['__names__'] = []
    for name, configs in yaml['connections'].items():
        connections[name] = compile_connection(name, configs)
        connections['__names__'].append(name)

    return CompiledClass('Connections', connections, parent='ActivatingContainer')


def compile_connection(name, configs):
    connection = dict()
    for key, value in configs.items():
        connection[key] = value

    return CompiledClass(name, connection, parent='Connection')


def compile_services(path):
    services = dict()

    stubs_path = find_pipe_path(path) + '/stubs.yaml'
    stubs_yaml = pyyaml.safe_load(open(stubs_path))
    unserviced_stubs = dict()

    for name, string in stubs_yaml['stubs'].items():
        service, stub = compile_stub(name, string)
        if unserviced_stubs.get(service, None) is None:
            unserviced_stubs[service] = dict()
        unserviced_stubs[service][name] = stub

    path = find_pipe_path(path) + 'services/'
    services['path'] = path

    services['__names__'] = []
    for name in next(os.walk(path))[1]:
        if not name.startswith(INVALID_PREFIXES):
            services['__names__'].append(name)

            stubs = unserviced_stubs.pop(name)
            services[name] = compile_service(path + name, name, stubs)

    return CompiledClass('Services', services, parent='ActivatingContainer')


def compile_service(service_path, name, stubs):
    service = dict()
    service['stubs'] = compile_stubs(stubs)

    path = service_path
    yaml = pyyaml.safe_load(open(path + '/service.yaml'))

    for key, value in yaml['service'].items():
        service[key] = value

    return CompiledClass(name, service, parent='Service')


def compile_stubs(stubs):
    names = []
    for stub_name in stubs.keys():
        names.append(stub_name)
    stubs['__names__'] = names

    return CompiledClass('Stubs', stubs, parent='ActivatingContainer')


def compile_stub(name, string):
    service, proto_in, proto_out, stub_out = parse_stub_string(string)

    if proto_in:
        vars()[proto_in] = CompiledClass.PlainString('messages_pb2.' + proto_in)
        proto_in = vars()[proto_in]

    if proto_out:
        vars()[proto_out] = CompiledClass.PlainString('messages_pb2.' + proto_out)
        proto_out = vars()[proto_out]

    return service, CompiledClass(name, vars(), parent='Stub')
