#!/usr/bin/env python

import argparse
from jinja2 import Environment, FileSystemLoader
import logging
import os
import requests
import shutil
import tempfile


logger = logging.getLogger('puzzler')


def generate_marathon_url(env):
    return "http://marathon.service.{}.consul/v2".format(env)


def setup_logging(level):
    ch = logging.StreamHandler()
    formatter = logging.Formatter('%(asctime)s %(levelname)s %(message)s')
    ch.setFormatter(formatter)
    logger.addHandler(ch)
    logger.setLevel(level)


def make_parser():
    parser = argparse.ArgumentParser(description="A tool to setup a minimesos config file")

    parser.add_argument('--numagents', default=1, type=int,
                        help="The number of mesos agents to create Default: %(default)r")
    parser.add_argument('--cpu', default=1,
                        help="The number of CPUs each mesos agent should have Default: %(default)r")
    parser.add_argument('--mem', default=256,
                        help="The amount of memory (in MB) each mesos agent should have Default: %(default)r")
    parser.add_argument('--cluster_template', default='templates/cluster.template',
                        help="The location of the cluster configuration template Default: %(default)r")
    parser.add_argument('--app_template', default='templates/app.template',
                        help="The location of the app configuration template Default: %(default)r")
    parser.add_argument('--name', default='test-cluster',
                        help="The name of the test cluster Default: %(default)r")
    parser.add_argument('--azcount', default=3, type=int,
                        help="The number of different az/racks to use as constraints Default %(default)r")
    parser.add_argument('--env', default='classicqa-useast1',
                        help="The environment to use as a template for tasks Default: %(default)r")
    parser.add_argument('--workdir', default=".",
                        help="The base directory to create the template files Default: %(default)r")
    parser.add_argument('--cleanup', default=False, action='store_true',
                        help="Cleanup the temporary directory with config files Default: %(default)r")

    parser.add_argument('--loglevel', default='WARNING', help="How verbose should we be Default: %(default)r")

    return parser


def main():
    # Get our command line arguments
    parser = make_parser()
    arguments = parser.parse_args()
    # Setup the logging
    setup_logging(arguments.loglevel)
    # Create the temporary directory to contain the output files
    tempdir = tempfile.mkdtemp(dir=arguments.workdir, prefix="minimesos-input.")
    logger.debug("Tempdir name: {}".format(tempdir))

    # open the template for the cluster configuration
    cluster_template_dir = os.path.dirname(os.path.abspath(arguments.cluster_template))
    cluster_template_file = os.path.basename(arguments.cluster_template)
    cluster_template_loader = FileSystemLoader(cluster_template_dir)
    cluster_template_env = Environment(loader=cluster_template_loader)
    cluster_template = cluster_template_env.get_template(cluster_template_file)

    agent_version = '0.28.1-0.1.0'

    logger.info("Creating a cluster config file with {} agents".format(arguments.numagents))
    cluster_file = open("{}/cluster_config".format(tempdir), "w")
    cluster_file.write(
        cluster_template.render(
            {'agent_count': arguments.numagents,
             'mem_count': arguments.mem,
             'cpu_count': arguments.cpu,
             'agent_version_tag': agent_version,
             'az_count': arguments.azcount,
             'config_name': arguments.name
             }
        )
    )
    cluster_file.close()

    for env in arguments.env.split(','):
        # Figure out the marathon url
        base_marathon_url = generate_marathon_url(env)
        logger.debug("Marathon Url: {}".format(base_marathon_url))

        logger.info("Getting the list of apps in {}".format(env))
        all_apps = []
        app_response = requests.get("{}/apps".format(base_marathon_url))
        app_json = app_response.json()
        for app in app_json['apps']:
            all_apps.append(app['id'])
        logger.debug("Found {} apps".format(len(all_apps)))

        # open the template for the app configuration
        app_template_dir = os.path.dirname(os.path.abspath(arguments.app_template))
        app_template_file = os.path.basename(arguments.app_template)
        app_template_loader = FileSystemLoader(app_template_dir)
        app_template_env = Environment(loader=app_template_loader)
        app_template = app_template_env.get_template(app_template_file)

        for app in sorted(all_apps):
            app_info_response = requests.get("{}/apps/{}".format(base_marathon_url, app))
            app_info = app_info_response.json()
            # remove the env from the app id
            # app_id = app.replace("/{}-".format(arguments.env), "")
            app_id = app.replace("/", "")
            logger.info("Writing config for {}".format(app_id))
            # open the file
            app_file = open("{}/app-{}".format(tempdir, app_id), "w")

            app_file.write(
                app_template.render(
                    {
                        "app_name": app_id,
                        "cpu_count": app_info['app']['cpus'],
                        "mem_count": app_info['app']['mem'],
                        'az_count': arguments.azcount,
                        "instance_count": app_info['app']['instances']
                    }
                )
            )
            app_file.close()

    if arguments.cleanup:
        shutil.rmtree(tempdir)

if __name__ == '__main__':
    main()
