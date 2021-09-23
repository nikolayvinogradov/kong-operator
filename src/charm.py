#!/usr/bin/env python3
# Copyright 2021 nickv
# See LICENSE file for licensing details.
#
# Learn more at: https://juju.is/docs/sdk

"""Charm the service.

Refer to the following post for a quick-start guide that will help you
develop a new k8s charm using the Operator Framework:

    https://discourse.charmhub.io/t/4208
"""

import logging
from urllib.parse import urljoin
import requests
from jinja2 import Environment, FileSystemLoader

from ops.charm import CharmBase
from ops.framework import StoredState
from ops.main import main
from ops.model import ActiveStatus, ModelError
from ops.pebble import ChangeError

logger = logging.getLogger(__name__)

KONG_ADMIN_API = '127.0.0.1:8444'
KONG_CONTAINER_NAME = 'kong'
KONG_PEBBLE_SERVICE_NAME = 'kong'
KONG_RELOAD_PEBBLE_SERVICE_NAME = 'kong-reload'
KONG_CONFIG_PATH = '/kong.conf'

class KongOperatorCharm(CharmBase):
    """Kong operator charm"""

    _stored = StoredState()

    def __init__(self, *args):
        super().__init__(*args)
        self.framework.observe(self.on.kong_pebble_ready, self._on_kong_pebble_ready)
        self.framework.observe(self.on.config_changed, self._on_config_changed)

        self._template_env = None

    def _kong_admin_post(self, path, data):
        """Sends API POST request to Kong Admin API.

        :param str path: The request path.
        :param dict data: POST request parameters.
        """
        request_url = urljoin('https://{}'.format(KONG_ADMIN_API), path)
        response = requests.post(url=request_url, data=data, verify=False)
        response.raise_for_status()

    def _kong_apply_config(self, container):
        """kong.conf generation based on Juju config

        :param object container: the container running Kong
        """

        # This dictionary could be also used to initialize Kong environment vars, so
        # we list most commonly used options here as an example.
        # see https://docs.konghq.com/gateway-oss/2.5.x/configuration/#environment-variables
        context = {
            "KONG_ADMIN_ACCESS_LOG":       "/dev/stdout",
            "KONG_ADMIN_ERROR_LOG":        "/dev/stderr",
            "KONG_ADMIN_GUI_ACCESS_LOG":   "/dev/stdout",
            "KONG_ADMIN_GUI_ERROR_LOG":    "/dev/stderr",
            "KONG_ADMIN_LISTEN":           "{} http2 ssl".format(KONG_ADMIN_API),
            "KONG_CLUSTER_LISTEN":         "off",
            "KONG_DATABASE":               "off",
            "KONG_KIC":                    "on",
            "KONG_LUA_PACKAGE_PATH":       "/opt/?.lua;/opt/?/init.lua;;",
            "KONG_NGINX_WORKER_PROCESSES": "2",
            "KONG_PLUGINS":                "bundled",
            "KONG_PORTAL_API_ACCESS_LOG":  "/dev/stdout",
            "KONG_PORTAL_API_ERROR_LOG":   "/dev/stderr",
            "KONG_PORT_MAPS":              "80:8000, 443:8443",
            "KONG_PREFIX":                 "/kong_prefix/",
            "KONG_PROXY_ACCESS_LOG":       "/dev/stdout",
            "KONG_PROXY_ERROR_LOG":        "/dev/stderr",
            "KONG_PROXY_LISTEN":           "0.0.0.0:8000, 0.0.0.0:8443 http2 ssl",
            "KONG_STATUS_LISTEN":          "0.0.0.0:8100",
            "KONG_STREAM_LISTEN":          "off",
            "KONG_NGINX_DAEMON":           "off",
            "KONG_MEM_CACHE_SIZE":         self.config["mem-cache-size"].strip(),
        }

        self._kong_render_config_and_push(container, 'kong.conf.j2', KONG_CONFIG_PATH, context=context)

    def _kong_apply_runtime_config(self, container):
        """TODO: This is workaround method that uses Kong admin API to load config.
        It is better to rework this to a configuration file.
        """
        if self.config["declarative-config"]:
            self._kong_admin_post('config', {'config': self.config["declarative-config"]})

    def _start_oneshot_service(self, container, service_name):
        try:
            container.start(service_name)
        except ChangeError as e:
            if not (e.change.kind == 'start' and e.change.status == 'Error'
                    and 'cannot start service: exited quickly with code 0' in e.err):
                raise Exception('failed to start a one-shot service') from e

    def _kong_render_config_and_push(self, container, template_name, target_path, context={}):
        if self._template_env is None:
            self._template_env = Environment(loader=FileSystemLoader(
                f'{self.charm_dir}/templates'))
        container.push(
            target_path,
            self._template_env.get_template(template_name).render(**context),
            make_dirs=True
        )

    def _get_kong_pebble_layer(self):
        result = {
            "summary": "kong proxy layer",
            "description": "Kong API Gateway layer",
            "services": {
                KONG_PEBBLE_SERVICE_NAME: {
                    "override": "replace",
                    "summary": "Kong API Gateway",
                    "command": "kong start -c /kong.conf",
                    "startup": "enabled",
#                    "environment": {} # the 'context' described above can be used here
                },
                KONG_RELOAD_PEBBLE_SERVICE_NAME: {
                    "override" : "replace",
                    "summary" : "Kong reload",
                    "command" : "kong reload -c /kong.conf",
                    "startup": "disabled"
                }
            }
        }

        return result

    def _on_kong_pebble_ready(self, event):
        # Get a reference the container attribute on the PebbleReadyEvent
        container = event.workload

        # Define an initial Pebble layer configuration
        pebble_layer = self._get_kong_pebble_layer()

        # Add intial Pebble config layer using the Pebble API
        container.add_layer("kong", pebble_layer, combine=True)
        # Autostart any services that were defined with startup: enabled and wait for them to start

        self._kong_apply_config(container)

        container.autostart()

        self._kong_apply_runtime_config(container)

        # Learn more about statuses in the SDK docs:
        # https://juju.is/docs/sdk/constructs#heading--statuses
        self.unit.status = ActiveStatus()

    def _on_config_changed(self, event):
        logger.info("Config change hook, updating Kong config")
        container = self.unit.get_container(KONG_CONTAINER_NAME)

        svc = None
        try:
            svc = container.get_service(KONG_PEBBLE_SERVICE_NAME)
        except:
            pass

        if not svc or not svc.is_running():
            logger.info("Service {} is not found or not running, postponing config change"
                .format(KONG_PEBBLE_SERVICE_NAME))
            event.defer()
            return

        self._kong_render_config_and_push(container, 'kong.conf.j2', KONG_CONFIG_PATH, context={})

        self._start_oneshot_service(container, KONG_RELOAD_PEBBLE_SERVICE_NAME)

        self._kong_apply_runtime_config(container)

if __name__ == "__main__":
    main(KongOperatorCharm)
