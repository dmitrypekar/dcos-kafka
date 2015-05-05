"""DCOS Kafka"""
from __future__ import print_function
import os
import pkg_resources
import requests
import sys
import subprocess
import toml
from dcos_kafka import constants

def marathon_app():
    dcos_config = os.getenv("DCOS_CONFIG")
    if dcos_config is None:
        raise CliError("Please specify DCOS_CONFIG env variable")

    with open(dcos_config) as f:
        config = toml.loads(f.read())

    marathon = config["marathon"]
    url = ("http://" + marathon["host"] + ":" + str(marathon["port"]) + "/v2/apps/kafka")

    response = requests.get(url, timeout=5)
    if response.status_code != 200:
        if response.status_code == 404: raise CliError("Kafka is not running")
        else: raise CliError("Unexpected status code: " + str(response.status_code))

    if 'app' not in response.json():
        raise CliError(response.json()['message'])

    return response.json()["app"]


def api_url():
    app = marathon_app()
    tasks = app['tasks']

    if len(tasks) == 0:
        raise CliError("Kafka is not running")

    task = tasks[0]
    return "http://" + task["host"] + ":" + str(task["ports"][0])


def find_java():
    def executable(file_path):
        return os.path.isfile(file_path) and os.access(file_path, os.X_OK)

    java_home = os.environ.get('JAVA_HOME')
    if java_home is not None and executable(java_home + "/bin/java"):
        return java_home + "/bin/java"

    if 'PATH' in os.environ:
        for path in os.environ['PATH'].split(os.pathsep):
            path = path.strip('"')
            java_file = os.path.join(path, 'java')
            if executable(java_file): return java_file

    raise CliError("This command requires Java to be installed. Please install JRE")


def find_jar():
    for f in pkg_resources.resource_listdir('dcos_kafka', None):
        if f.startswith("kafka-mesos") and f.endswith(".jar"):
            return pkg_resources.resource_filename('dcos_kafka', f)

    raise CliError("kafka-mesos*.jar not found in package resources")


def run(args):
    help = len(args) > 0 and args[0] == "--help"
    if help: args[0] = "help"

    command = [find_java(), "-jar", find_jar()]
    command.extend(args)

    env = {"KM_NO_SCHEDULER" : "true"}
    if not help: env["KM_API"] = api_url()

    process = subprocess.Popen(
        command,
        env=env,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE)

    stdout, stderr = process.communicate()
    print(stdout.decode("utf-8"), end="")
    print(stderr.decode("utf-8"), end="", file=sys.stderr)

    return process.returncode


class CliError(Exception): pass


def main():
    args = sys.argv[2:] # remove dcos-kafka & kafka
    if len(args) == 1 and args[0] == "--info":
        print("Start and manage Kafka brokers")
        return 0

    if len(args) == 1 and args[0] == "--version":
        print(constants.version)
        return 0

    if len(args) == 1 and args[0] == "--config-schema":
        print("{}")
        return 0

    if "--help" in args or "-h" in args:
        if "--help" in args: args.remove("--help")
        if "-h" in args: args.remove("-h")
        args.insert(0, "help")

    try:
        return run(args)
    except CliError as e:
        print("Error: " + str(e), file=sys.stderr)
        return 1
