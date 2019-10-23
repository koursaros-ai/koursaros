from gnes.flow import *
import pathlib
import functools

_Flow = Flow
DEFAULT_IMAGE = 'gnes/gnes:latest-alpine'


class Flow(_Flow):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.client_node = {}

    def add_client(self, **kwargs):
        self.client_node = dict(
            app='client',
            model=kwargs['name'],
            image='hub-client:latest-%s' % kwargs['name'],
            yaml_path=kwargs['yaml_path']
        )
        return self

    def add(self, service: Union['Service', str], name: str = None, *args, **kwargs):
        supercall = functools.partial(super().add, service, name, *args, **kwargs)
        app = service.name.lower()
        model = name if name else 'base'
        yaml_path = kwargs.get('yaml_path', None)

        if model == 'base' or yaml_path.isidentifier():
            ret = supercall()
            image = DEFAULT_IMAGE
        else:
            # ignore invalid yaml path
            path = pathlib.Path(yaml_path)
            path.touch()
            ret = supercall()
            path.unlink()
            image = 'hub-%s:latest-%s' % (app, model)

        # add custom kwargs
        try:
            name = name if name else '%s%d' % (service, self._service_name_counter[service]-1)

            v = ret._service_nodes[name]
            v['storage'] = kwargs.get('storage', '500Mi')
            v['memory'] = kwargs.get('storage', '500Mi')
            v['cpu'] = kwargs.get('storage', '300m')
            v['replicas'] = kwargs.get('replicas', 1)
            v['app'] = app
            v['model'] = model
            v['image'] = image
        except Exception as e:
            print(e)
            import pdb; pdb.set_trace()
        return ret

    @staticmethod
    def yaml_stream(yml):
        from ruamel.yaml import YAML, StringIO
        _yaml = YAML()
        stream = StringIO()
        _yaml.dump(yml, stream)
        return stream.getvalue().strip()

    @build_required(BuildLevel.GRAPH)
    def get_service_command(self, name):
        v = self._service_nodes[name]

        defaults_kwargs, _ = service_map[
            v['service']]['parser']().parse_known_args(['--yaml_path', 'TrainableBase'])

        non_default_kwargs = {
            k: v for k, v in vars(v['parsed_args']).items() if getattr(defaults_kwargs, k) != v}

        if not isinstance(non_default_kwargs.get('yaml_path', ''), str):
            non_default_kwargs['yaml_path'] = v['kwargs']['yaml_path']

        command = '' if v['image'] != DEFAULT_IMAGE else service_map[v['service']]['cmd'] + ' '
        command += ' '.join(['--%s %s' % (k, v) for k, v in non_default_kwargs.items()])
        return command

    @build_required(BuildLevel.GRAPH)
    def to_swarm_yaml(self) -> str:
        """
        Generate the docker swarm YAML compose file
        :return: the generated YAML compose file
        """

        swarm_yml = {'version': '3.4',
                     'services': {}}

        for name, node in self._service_nodes.items():
            swarm_yml['services'][name] = dict(
                image=node['image'],
                command=self.get_service_command(name)
            )
            if node['replicas'] > 1:
                swarm_yml['services'][name]['deploy'] = {'replicas': node['replicas']}
            ports = vars(node['parsed_args']).get('grpc_port', None)
            if ports:
                swarm_yml['services'][name]['ports'] = [ports]

        return self.yaml_stream(swarm_yml)

    @build_required(BuildLevel.GRAPH)
    def to_helm_yaml(self):
        self.helm_yaml = defaultdict(lambda: [])

        for name, node in self._service_nodes.items():
            command = self.get_service_command(name)
            p_args = vars(node['parsed_args'])

            self.helm_yaml[node['app']] += [dict(
                name=name,
                app=node['app'],
                model=node['model'],
                port_in=p_args.get('port_in', None),
                port_out=p_args.get('port_out', None),
                ctrl_port=p_args.get('ctrl_port', None),
                grpc_port=p_args.get('grpc_port', None),
                command=command.split(),
                replicas=node['replicas'],
                storage=node['storage'],
                memory=node['memory'],
                cpu=node['cpu'],
                image=node['image']
            )]

        self.helm_yaml = dict(services=dict(self.helm_yaml))
        return self.yaml_stream(self.helm_yaml)

