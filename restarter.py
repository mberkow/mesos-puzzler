#!/usr/bin/env python

import argparse
import logging
import requests
import sys
import time

logger = logging.getLogger('restarter')


def setup_logging(level):
    ch = logging.StreamHandler()
    formatter = logging.Formatter('%(asctime)s %(levelname)s %(message)s')
    ch.setFormatter(formatter)
    logger.addHandler(ch)
    logger.setLevel(level)


def make_parser():
    parser = argparse.ArgumentParser(description="A tool to restart the local marathon apps")

    parser.add_argument('--loglevel', default='WARNING', help="How verbose should we be Default: %(default)r")

    return parser


def main():
    # Get our command line arguments
    parser = make_parser()
    arguments = parser.parse_args()
    # Setup the logging
    setup_logging(arguments.loglevel)

    all_apps = []
    app_response = requests.get("http://boot2docker:8080/v2/apps")
    app_json = app_response.json()
    for app in app_json['apps']:
        all_apps.append(app['id'])
    logger.debug("Found {} apps".format(len(all_apps)))
    for app in all_apps:
        logger.info("Restarting {}".format(app))
        restart_response = requests.post("http://boot2docker:8080/v2/apps{}/restart".format(app))

        restart_json = restart_response.json()

        deployment_id = restart_json['deploymentId']
        logger.debug("Deployment ID {}".format(deployment_id))
        inflight = 1
        time.sleep(1)

        while inflight:

            app_response = requests.get("http://boot2docker:8080/v2/apps{}".format(app))
            app_json = app_response.json()
            if app_json['app']['deployments']:
                logger.debug("Found deployment {} for {}".format(app_json['app']['deployments'][0]['id'], app))
                inflight = 1
                time.sleep(2)
            else:
                inflight = 0


if __name__ == '__main__':
    main()
