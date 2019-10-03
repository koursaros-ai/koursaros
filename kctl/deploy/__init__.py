

from subprocess import Popen
from kctl.utils import BOLD
import signal
import sys
import os


def get_pipeline(name):
    import koursaros.pipelines
    pipeline = getattr(koursaros.pipelines, name)
    return pipeline(None)


def deploy_pipeline(pipe_path, args):
    os.chdir(pipe_path + '..')
    pipeline = get_pipeline(args.pipeline_name)
    deploy(pipeline.Services, pipe_path)


def deploy_service(pipe_path, args):
    pipeline = get_pipeline(args.pipeline_name)
    service = getattr(pipeline.Services, args.service_name)
    deploy([service], pipe_path)


def deploy(services, pipe_path):
    processes = []

    try:
        for service in services:
            service_cls = service.__class__.__name__
            cmd = [sys.executable, '-m', f'{pipe_path}.services.{service_cls}'] + sys.argv[1:]
            print(f'''Running "{BOLD.format(' '.join(cmd))}"...''')
            p = Popen(cmd)

            processes.append((p, service_cls))

            for p, service_cls in processes:
                p.communicate()

    except KeyboardInterrupt:
        pass
    except Exception as exc:
        print(exc)

    finally:
        for p, service_cls in processes:

            if p.poll() is None:
                os.kill(p.pid, signal.SIGTERM)
                print(f'Killing pid {p.pid}: {service_cls}')
            else:
                print(f'process {p.pid}: "{service_cls}" ended...')


