# Kong operator

## Description

Kong API Gateway is an NGINX-based API Gateway with Lua-scripted run-time engine that enables advanced features like dynamic reconfiguration via simple REST API. It can be deployed as a standalone application for in-memory state management or with the database backend. The latter enables the use of REST API to dynamically perform CRUD operations on the gateway objects (services, routes, etc.) Kong supports deployment with an Ingress controller that enables the use of the Kubernetes-native interfaces to requests routing in Kong.

Kong supports pluggable modules providing additional features, like authentication, rate-limiting, request transformations and other.

This charm currently supports deployment of Kong v.2.5 using the upstream Docker image in database-less mode. Refer to [this page](https://docs.konghq.com/gateway-oss/2.5.x/db-less-and-declarative-config/#using-kong-in-db-less-mode) for the list of features and limitations.

## Usage and Configuration example

    $ curl <kong_pod_ip>:8000
    {"message":"no Route matched with those values"}

Once the operator is deployed, request routing configuration can be loaded via ```kong-declarative``` charm configuration option. You can obtain initial ```kong.yml``` by running:

     kubectl exec -it -n kong kong-operator-0 -c proxy -- sh -c "rm /kong.yml && kong config init && cat /kong.yml"

Example config file with a service and a route (see also [Kong OSS Gateway docs](https://docs.konghq.com/gateway-oss/2.5.x/db-less-and-declarative-config/)):

    $ cat <<EOF > kong.yml
    _format_version: "2.1"
    
    _transform: true
    
    services:
    - name: example-service
      url: http://mockbin.org
      routes:
      - name: example-route
        paths:
        - /
    EOF

Load the configuration into Kong via the operator:

    juju config kong-operator declarative-config=$(cat kong.yml)

## Relations

None at the moment.

## OCI Images

Images used:

- [kong:2.5](https://konghq.com/blog/kong-gateway-oss-2-5/)

## Development setup

To set up a local test environment with [Microk8s](https://microk8s.io/docs):

    # Install MicroK8s
    $ sudo snap install --classic microk8s
    
    # Wait for MicroK8s to be ready
    $ sudo microk8s status --wait-ready
    
    # Enable features required by Juju controller & charm
    $ sudo microk8s enable storage dns
    
    # (Optional) Alias kubectl bundled with MicroK8s package
    $ sudo snap alias microk8s.kubectl kubectl
    
    # (Optional) Add current user to 'microk8s' group
    # This avoid needing to use 'sudo' with the 'microk8s' command
    $ sudo usermod -aG microk8s $(whoami)
    
    # Activate the new group (in the current shell only)
    # Log out and log back in to make the change system-wide
    $ newgrp microk8s
    
    # Install Charmcraft
    $ sudo snap install charmcraft

    # Build the charm
    $ charmcraft build
    
    # Install juju
    $ sudo snap install --classic juju
    
    # Bootstrap the Juju controller on MicroK8s
    $ juju bootstrap microk8s micro

    # Deploy the charm package 
    $ juju deploy ./kong-operator_ubuntu-20.04-amd64.charm --resource kong-image=kong:2.5

    # Do some changes, and rebuild charm
    $ rm -rf build && charmcraft build

    # Upgrade operator
    $ juju upgrade-charm kong-operator --path ./kong-operator_ubuntu-20.04-amd64.charm


## Future ideas

Following improvements can be implement to extend the capabilities of this charm:

- Service ports
- Relation to backend applications to implement
- Relation to PostgreSQL charm to enable CRUD for Kong configuration objects
- Kong Ingress Controller operator charm and the ingress-type relation to this charm
- Once central database relation is implement, Kong clustering implementation is unblocked
- Plugins automation

## Contributing

Please see the [Juju SDK docs](https://juju.is/docs/sdk) for guidelines 
on enhancements to this charm following best practice guidelines, and
`CONTRIBUTING.md` for developer guidance.
