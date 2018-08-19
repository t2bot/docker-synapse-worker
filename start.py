#!/usr/local/bin/python

import os
import os.path
import yaml
import socket
from string import Template
from shutil import copyfile

RUNTIME_DIR = "/synapse_runtime"
TEMPLATE_DIR="/synapse/templates"
DATA_DIR = "/data"
MEDIA_DIR = "/synapse_media"

NEEDS_CLIENT_LISTENER = [
    'synapse.app.synchrotron', 
    'synapse.app.client_reader',
    'synapse.app.user_dir',
    'synapse.app.frontend_proxy',
    'synapse.app.event_creator',
    'synapse.app.media_repository',
]
NEEDS_FEDERATION_LISTENER = [
    'synapse.app.federation_reader',
]
ALL_WORKERS = [
    'synapse.app.homeserver',
    'synapse.app.pusher',
    'synapse.app.appservice',
    'synapse.app.federation_sender',
] + NEEDS_CLIENT_LISTENER + NEEDS_FEDERATION_LISTENER

UID = os.getenv("UID", 991)
GID = os.getenv("GID", 991)

hostname = os.getenv("SYNAPSE_HOSTNAME", socket.gethostname())
worker = os.getenv("SYNAPSE_WORKER", "")
log_level = os.getenv("SYNAPSE_LOG_LEVEL", "INFO")
repl_host = os.getenv("SYNAPSE_REPLICATION_HOST", "")
cpu_affinity = os.getenv("SYNAPSE_CPU_AFFINITY", "")

if cpu_affinity == "":
    cpu_affinity = None

if worker not in ALL_WORKERS:
    raise "unknown worker requested: %s" % worker
if (not repl_host or repl_host == "") and worker != 'synapse.app.homeserver':
    raise "no replication host given"

tmpl_vars = {
    'app_name': worker,
    'hostname': hostname,
    'log_level': log_level,
    'repl_host': repl_host,
}

# Copy the certificates/keys
copyfile(os.path.join(DATA_DIR, "tls.crt"), os.path.join(RUNTIME_DIR, "tls.crt"))
copyfile(os.path.join(DATA_DIR, "tls.key"), os.path.join(RUNTIME_DIR, "tls.key"))
copyfile(os.path.join(DATA_DIR, "tls.dh"), os.path.join(RUNTIME_DIR, "tls.dh"))
copyfile(os.path.join(DATA_DIR, "signing.key"), os.path.join(RUNTIME_DIR, "signing.key"))

# Write the log config first
with open(os.path.join(TEMPLATE_DIR, "log.config"), 'r') as f:
    tmpl = Template(f.read())
    templated = tmpl.substitute(tmpl_vars)
    with open(os.path.join(RUNTIME_DIR, "log.config"), 'w') as f2:
        f2.write(templated)

# Write the worker config
worker_conf = {
    'worker_app': worker,
    'worker_daemonize': False,
}
if worker != 'synapse.app.homeserver':
    worker_conf["worker_replication_host"] = repl_host
    worker_conf["worker_replication_port"] = 9092
    worker_conf["worker_replication_http_port"] = 9093
    worker_conf["worker_replication_url"] = "http://%s:9093/_synapse/replication" % repl_host
    worker_conf["worker_main_http_uri"] = "http://%s:8008" % repl_host
    worker_conf["worker_pid_file"] = os.path.join(RUNTIME_DIR, "worker.pid")
    worker_conf["worker_log_config"] = os.path.join(RUNTIME_DIR, "log.config")
    
    listeners = [{
        'type': 'http',
        'port': 9000,
        'tls': False,
        'bind_address': '0.0.0.0',
        'x_forwarded': True,
        'resources': [
            {
                'names': ['metrics'],
                'compress': False,
            },
        ],
    }]
    if worker in NEEDS_CLIENT_LISTENER:
        listeners.append({
            'type': 'http',
            'port': 8008,
            'tls': False,
            'bind_address': '0.0.0.0',
            'x_forwarded': True,
            'resources': [
                {
                    'names': ['client'],
                    'compress': True,
                },
                {
                    'names': ['media'],
                    'compress': False,
                },
            ],
        })
    if worker in NEEDS_FEDERATION_LISTENER:
        listeners.append({
            'type': 'http',
            'port': 8448,
            'tls': True,
            'bind_address': '0.0.0.0',
            'x_forwarded': True,
            'resources': [
                {
                    'names': ['federation'],
                    'compress': False,
                },
            ],
        })
    worker_conf['worker_listeners'] = listeners
    if cpu_affinity is not None:
        worker_conf["worker_cpu_affinity"] = cpu_affinity
with open(os.path.join(RUNTIME_DIR, "worker.yaml"), 'w') as f:
    yaml.dump(worker_conf, f)

# Write the homeserver config
with open(os.path.join(DATA_DIR, "homeserver.yaml"), 'r') as f:
    hs_conf = yaml.load(f.read())
    if cpu_affinity is not None:
        hs_conf["cpu_affinity"] = cpu_affinity
    else:
        hs_conf.pop("cpu_affinity", None)
    hs_conf["tls_certificate_path"] = os.path.join(RUNTIME_DIR, "tls.crt")
    hs_conf["tls_private_key_path"] = os.path.join(RUNTIME_DIR, "tls.key")
    hs_conf["tls_dh_params_path"] = os.path.join(RUNTIME_DIR, "tls.dh")
    hs_conf["pid_file"] = os.path.join(RUNTIME_DIR, "synapse.pid")
    hs_conf["web_client"] = False
    hs_conf["no_tls"] = False
    hs_conf["enable_metrics"] = True
    hs_conf["log_file"] = "/dev/null"
    hs_conf["log_config"] = os.path.join(RUNTIME_DIR, "log.config")
    hs_conf["media_store_path"] = os.path.join(MEDIA_DIR, "media_store")
    hs_conf["upload_path"] = os.path.join(MEDIA_DIR, "uploads")
    hs_conf["signing_key_path"] = os.path.join(RUNTIME_DIR, "signing.key")
    hs_conf["listeners"] = [
        {
            'type': 'http',
            'port': 8008,
            'tls': False,
            'x_forwarded': True,
            'bind_address': '0.0.0.0',
            'resources': [
                {
                    'names': ['client'],
                    'compress': True,
                },
                {
                    'names': ['federation', 'media'],
                    'compress': False,
                },
            ],
        },
        {
            'type': 'http',
            'port': 8448,
            'tls': True,
            'x_forwarded': True,
            'bind_address': '0.0.0.0',
            'resources': [
                {
                    'names': ['federation', 'media'],
                    'compress': False,
                },
            ],
        },
        {
            'type': 'http',
            'port': 9000,
            'tls': False,
            'x_forwarded': True,
            'bind_address': '0.0.0.0',
            'resources': [
                {
                    'names': ['metrics'],
                    'compress': False,
                },
            ],
        },
        {
            'type': 'replication',
            'port': 9092,
            'bind_address': '0.0.0.0',
        },
        {
            'type': 'http',
            'port': 9093,
            'tls': False,
            'x_forwarded': False,
            'bind_address': '0.0.0.0',
            'resources': [
                {
                    'names': ['replication'],
                    'compress': False,
                },
            ],
        },
    ]
    with open(os.path.join(RUNTIME_DIR, "homeserver.yaml"), 'w') as f2:
        yaml.dump(hs_conf, f2)


# Finally, start the worker
ownership = "{}:{}".format(UID, GID)
args = ['python', '-m', worker, '-c', os.path.join(RUNTIME_DIR, "homeserver.yaml"), '-c', os.path.join(RUNTIME_DIR, "worker.yaml")]
os.execv("/sbin/su-exec", ["su-exec", ownership] + args)
