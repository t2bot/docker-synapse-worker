# docker-synapse-worker

A docker image for a [synapse](https://github.com/matrix-org/synapse) worker.

Available on Docker Hub as [t2bot/synapse-worker](https://hub.docker.com/r/t2bot/synapse-worker).

Please read the [documentation for workers](https://github.com/matrix-org/synapse/blob/master/docs/workers.rst) before using this project. This project assumes you have a fair amount of experience with the operation of synapse and are prepared to use workers in a containerized environment. This project is not intended to be used by inexperienced worker users.

# Building with a custom synapse

There are two build arguments available: The branch name and repo slug to build. By default, the repo slug is `matrix-org/synapse` and the branch is `master`. These can be changed like so:

```
docker build -t t2bot/synapse-worker --build-arg SYNAPSE_REPO_SLUG=matrix-org/synapse --build-arg SYNAPSE_BRANCH=master .
```

# Running

There are several workers available, all of which have their own port mappings you'll need to handle for your environment.

The following items should be available prior to starting a worker container:
* Signing and TLS keys should already be generated.
* A `homeserver.yaml` that is pre-configured for workers.

All containers expose the following ports and should be remapped to your needs:
* `8008` - Client APIs (http)
* `8448` - Federation APIs (https)
* `9000` - Metrics (http)

Additional ports, such as replication, will be bound as per the `homeserver.yaml` configuration and should not be forwarded to the host. Instead, a docker network should be created. The remainder of this document assumes you've created a network named `synapse`.

It is recommended that a reverse proxy be placed in front of both your federation and client-server APIs. This will allow you to change the worker locations more easily and route traffic to them. Setting up that reverse proxy is left as an exercise to the reader, however it is generally recommended to place the reverse proxy inside the `synapse` network and expose ports 443 and 8448 through that rather than use the `-p` flag on the worker containers.

### Assumptions on all worker containers

To reduce the amount of duplication in this documentation, it is assumed that you know how to start a docker container in your environment. This means you're expected to set up the appropriate port mappings (`-p 8448:8448` for example) and volume locations for your environment. 

All of the workers need the following files mapped via volumes:
* `/data/homeserver.yaml` (some variables, such as log configuration and listeners, may be overwritten)
* `/data/signing.key` (usually generated as `example.com.signing.key`)
* `/data/tls.crt` (usually generated as `example.com.tls.crt`)
* `/data/tls.dh` (usually generated as `example.com.tls.dh`)
* `/data/tls.key` (usually generated as `example.com.tls.key`)

Some notable things ignored in the configuration are:
* The logging configuration. Instead, the worker will only log to the console and not bind a file handler. The level at which this happens can be set via the `SYNAPSE_LOG_LEVEL` environment variable (defaults to `INFO`).
* The TCP and HTTP replication ports will be hardcoded to `9092` and `9093` respectively, and bound to `0.0.0.0` so they can be used by other containers. These must not be exposed to the outside world as the replication streams are not authenticated. If you are exposing these ports on the host, be sure to have strict network security to ensure that the wider world cannot influence the replication streams.
* The client and federation listeners will be hardcoded to `8008` and `8448` respectively, and bound to `0.0.0.0`. Additionally, they will have `x_forwarded: true` for their configuration.
* The metrics listener will be hardcoded to `9000` and bound to `0.0.0.0`. This will also have `x_forwarded: true` on it. This should only be exposed externally if you'd like the statistics public, as this is unauthenticated.

It is up to you to ensure that any special requirements are met for your workers. For example, if you're using a federation sender and fail to set the `send_federation: false` flag in your `homeserver.yaml` then the worker may fail to start, or break in bad ways. Always double check your configuration before starting a worker.

### Restarting/stopping the stack

Always ensure the main process starts first, followed by the workers. When restarting or shutting down the stack, stop the workers first then the main process last. It is generally unsafe to restart workers individually or independently of the whole stack.

### Workers

All the workers are configured via a `SYNAPSE_WORKER` environment variable. This is set to the worker application that should be started. All the workers, with the exception of the main process, need an additional environment variable to tell it where to look for replication host. The replication host is configured as `SYNAPSE_REPLICATION_HOST`.

As an example, if you set up a `SYNAPSE_WORKER=synapse.app.homeserver` container in the `synapse` network with the name `synapse-homeserver`, then any other workers would need `SYNAPSE_REPLICATION_HOST=synapse-homeserver` assuming they were also in the `synapse` network.

The media repository is mounted at `/synapse_media` on the container. If you're referencing application service registration files, be sure they point at a mounted volume.

All workers support a `SYNAPSE_CPU_AFFINITY` variable that is passed directly to the `cpu_affinity` or `worker_cpu_affinity` configuration variable.

The hostname used in the logs can be overridden with the `SYNAPSE_HOSTNAME` variable. Otherwise whatever Docker sets as the container's hostname will be used.

**Supported workers**:

| Application                     | Ports bound      |
|---------------------------------|------------------|
| `synapse.app.homeserver`        | 8008, 8448, 9000 |
| `synapse.app.pusher`            | 9000             |
| `synapse.app.synchrotron`       | 8008, 9000       |
| `synapse.app.appservice`        | 9000             |
| `synapse.app.federation_reader` | 8448, 9000       |
| `synapse.app.federation_sender` | 9000             |
| `synapse.app.media_repository`  | 8008, 9000       |
| `synapse.app.client_reader`     | 8008, 9000       |
| `synapse.app.user_dir`          | 8008, 9000       |
| `synapse.app.frontend_proxy`    | 8008, 9000       |
| `synapse.app.event_creator`     | 8008, 9000       |
