

from koursaros.utils import find_pipe_path
import os

PIPE_PATH = find_pipe_path(os.getcwd())
__location__ = os.path.dirname(__file__)


class KctlError(Exception):
    pass


def deploy_app(args):
    print('hello')
    raise NotImplementedError


def save_pipeline(args):
    from koursaros.compile import compile_pipeline
    compile_pipeline(PIPE_PATH)


def deploy_pipeline(args):

    if PIPE_PATH is None:
        raise KctlError('Current working directory is not an app')

    # 1. Compile pipeline
    save_pipeline(args)

    # 2. Check stubs.yaml, messages.proto, and rmq
    from kctl.deploy.checks import check_stubs, check_rabbitmq
    check_stubs(args)
    check_rabbitmq(args)

    # 3. Rebind services
    if args.rebind:
        from kctl.deploy.rabbitmq import bind_rabbitmq
        bind_rabbitmq(args)

    # 4. Deploy pipeline
    from .deploy import deploy_pipeline
    deploy_pipeline(PIPE_PATH, args)


    # else:
    #     from .create import build_trigger
    #     from .create import build_cloudbuild
    #     from .create import build_deployment
    #     from .create import build_dockerfile
    #     from .create import git_push
    #
    #     import uuid
    #     tag = str(uuid.uuid4())[:8]
    #
    #     if pushargs.all:
    #         build_trigger(all=True)
    #         build_cloudbuild(tag, all=True)
    #         build_dockerfile(all=True)
    #         build_deployment(tag, all=True)
    #         git_push(all=True)
    #
    #     else:
    #         microservices = pushargs.microservices
    #         build_trigger(microservices=microservices)
    #         build_cloudbuild(tag, microservices=microservices)
    #         build_dockerfile(microservices=microservices)
    #         build_deployment(tag, microservices=microservices)
    #         git_push(microservices=microservices)


def create_app(args):

    if APP_PATH is not None:
        raise KctlError('Current working directory is already an app')

    new_app_path = f'{os.getcwd()}/{args.name}'

    from shutil import copytree
    copytree(f'{__location__}/create/template/app', new_app_path)
    os.makedirs(f'{new_app_path}/.koursaros', exist_ok=True)
    open(f'{new_app_path}/.koursaros/__init__.py', 'w')
    print(f'Created app: {new_app_path}')


def create_pipeline(args):

    if APP_PATH is None:
        raise KctlError('Current working directory is not an app')

    pipelines_path = APP_PATH + '/pipelines/'

    os.makedirs(pipelines_path, exist_ok=True)
    new_pipeline_path = pipelines_path + args.name

    from shutil import copytree
    copytree(f'{__location__}/create/template/app/pipelines/pipeline', new_pipeline_path)
    print(f'Created pipeline: {new_pipeline_path}')


def create_service(args):

    if APP_PATH is None:
        raise KctlError('Current working directory is not an app')

    services_path = APP_PATH + '/services/'

    os.makedirs(services_path, exist_ok=True)
    new_service_path = services_path + args.name

    from shutil import copytree
    copytree(f'{__location__}/create/template/app/services/backend', new_service_path)
    print(f'Created backend: {new_service_path}')


def train_model(args):
    raise NotImplementedError


def pull_app(args):

    if APP_PATH is not None:
        raise KctlError('Current working directory is already an app')

    from subprocess import call
    call(['git', 'clone', args.git, args.name])

    if args.dir:
        from shutil import rmtree, copytree
        copytree(f'{args.name}/{args.dir}', '.kctlcache')
        rmtree(args.name)
        copytree('.kctlcache', args.name)
        rmtree('.kctlcache')


def get_args():
    from .logger import redirect_out
    redirect_out('kctl')

    import argparse
    from .constants import DESCRIPTION

    # kctl
    kctl_parser = argparse.ArgumentParser(description=DESCRIPTION, prog='kctl')
    kctl_subparsers = kctl_parser.add_subparsers()

    # kctl save
    kctl_save_parser = kctl_subparsers.add_parser(
        'save', description='compile and save to koursaros path'
    )
    kctl_save_subparsers = kctl_save_parser.add_subparsers()
    # kctl save pipeline
    kctl_save_pipeline_parser = kctl_save_subparsers.add_parser('pipeline')
    kctl_save_pipeline_parser.set_defaults(func=save_pipeline)

    # kctl create
    kctl_create_parser = kctl_subparsers.add_parser(
        'create', description='create an app, pipeline, backend, or model'
    )
    kctl_create_subparsers = kctl_create_parser.add_subparsers()
    # kctl create app
    kctl_create_app_parser = kctl_create_subparsers.add_parser('app')
    kctl_create_app_parser.set_defaults(func=create_app)
    kctl_create_app_parser.add_argument('name')
    # kctl create pipeline
    kctl_create_pipeline_parser = kctl_create_subparsers.add_parser('pipeline')
    kctl_create_pipeline_parser.set_defaults(func=create_pipeline)
    kctl_create_pipeline_parser.add_argument('name')
    # kctl create backend
    kctl_create_service_parser = kctl_create_subparsers.add_parser('backend')
    kctl_create_service_parser.set_defaults(func=create_service)
    kctl_create_service_parser.add_argument('name')

    # kctl train
    kctl_train_parser = kctl_subparsers.add_parser(
        'train', description='train a model'
    )
    kctl_train_subparsers = kctl_train_parser.add_subparsers()
    # kctl train model
    kctl_train_model_parser = kctl_train_subparsers.add_parser('model')
    kctl_train_model_parser.set_defaults(func=train_model)
    kctl_train_model_parser.add_argument('name')
    kctl_train_model_parser.add_argument('--base_image', default='koursaros-base')

    # kctl deploy
    kctl_deploy_parser = kctl_subparsers.add_parser(
        'deploy', description='deploy an app or pipeline'
    )
    kctl_deploy_subparsers = kctl_deploy_parser.add_subparsers()
    c_args = ('-c', '--connection')
    c_kwargs = {
        'action': 'store', 'required': True,
        'help': 'connection parameters to use from connections.yaml',
    }
    r_args = ('-r', '--rebind')
    r_kwargs = {
        'action': 'store_true',
        'help': 'clear and rebind the rabbitmq binds on entrance'
    }
    # kctl deploy app
    kctl_deploy_app_parser = kctl_deploy_subparsers.add_parser('app')
    kctl_deploy_app_parser.set_defaults(func=deploy_app)
    kctl_deploy_app_parser.add_argument(*c_args, **c_kwargs)
    kctl_deploy_app_parser.add_argument(*r_args, **r_kwargs)
    # kctl deploy pipeline
    kctl_deploy_pipeline_parser = kctl_deploy_subparsers.add_parser('pipeline')
    kctl_deploy_pipeline_parser.set_defaults(func=deploy_pipeline)
    kctl_deploy_pipeline_parser.add_argument('pipeline')
    kctl_deploy_pipeline_parser.add_argument(*c_args, **c_kwargs)
    kctl_deploy_pipeline_parser.add_argument(*r_args, **r_kwargs)

    # kctl pull
    kctl_pull_parser = kctl_subparsers.add_parser(
        'pull', description='pull an app'
    )
    kctl_pull_subparsers = kctl_pull_parser.add_subparsers()
    # kctl pull app
    kctl_pull_app_parser = kctl_pull_subparsers.add_parser('app')
    kctl_pull_app_parser.set_defaults(func=pull_app)
    kctl_pull_app_parser.add_argument('name')
    kctl_pull_app_parser.add_argument(
        '-g', '--git', action='store', help='pull an app from a git directory'
    )
    kctl_pull_app_parser.add_argument(
        '-d', '--dir', action='store', help='which directory the app is in'
    )

    return kctl_parser.parse_args()
