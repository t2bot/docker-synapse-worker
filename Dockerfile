FROM docker.io/python:2-alpine3.8

# Deps are essentially copy/paste from the synapse official image
RUN apk add --no-cache --virtual .nacl_deps \
        build-base \
        libffi-dev \
        libjpeg-turbo-dev \
        libressl-dev \
        libxslt-dev \
        linux-headers \
        postgresql-dev \
        su-exec \
        zlib-dev \
        ca-certificates \
    && pip install --upgrade pip setuptools lxml psycopg2

# Introduce user space things here so we can cache the install layer
ARG SYNAPSE_BRANCH=release-v0.33.8
ARG SYNAPSE_REPO_SLUG=matrix-org/synapse
RUN mkdir -p /synapse_runtime
RUN pip install --upgrade --process-dependency-links https://github.com/${SYNAPSE_REPO_SLUG}/tarball/${SYNAPSE_BRANCH}

ENV SYNAPSE_LOG_LEVEL=INFO
ENV SYNAPSE_WORKER=
ENV SYNAPSE_REPLICATION_HOST=
ENV SYNAPSE_CPU_AFFINITY=

EXPOSE 8008/tcp
EXPOSE 8448/tcp
EXPOSE 9000/tcp
EXPOSE 9092/tcp
EXPOSE 9093/tcp

# We're expecting the following in the volume dir:
#    homeserver.yaml
#    signing.key
#    tls.crt
#    tls.dh
#    tls.key
VOLUME ["/data", "/synapse_media"]

COPY . /synapse
RUN chmod +x /synapse/start.py
STOPSIGNAL SIGTERM
CMD ["/synapse/start.py"]
