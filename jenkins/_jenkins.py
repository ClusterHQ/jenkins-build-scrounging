# Copyright (c) ClusterHQ Ltd. See LICENSE for details.

import os

import treq
from twisted.internet import defer


BASE_URL = 'http://ci-live.clusterhq.com:8080/'
MAX_CONCURRENT_REQUESTS = 5

PASSWORD_ENV_VAR = 'JENKINS_PASSWORD'


def jenkins_get(path):
    password = os.environ.get(PASSWORD_ENV_VAR, None)
    if password is None:
        raise AssertionError(
            "Please specify the jenkins admin password the "
            "{} env var.".format(PASSWORD_ENV_VAR)
        )
    user = os.environ.get('JENKINS_USER', 'admin')
    return treq.get(BASE_URL + path, auth=(user, password))


class RequestFailed(Exception):

    def __init__(self, response):
        self.response = response

    def __str__(self):
        return "Request failed with code {}".format(self.response.code)


def jenkins_json_get(path):
    def decode_json(resp):
        if resp.code != 200:
            raise RequestFailed(resp)
        return resp.json()
    return jenkins_get(path).addCallback(decode_json)


def get_console_text(job_url):
    def content_for_200(resp):
        if resp.code == 200:
            return resp.content()
        return defer.succeed(None)
    return jenkins_get(job_url + '/consoleText').addCallback(content_for_200)


def get_test_report(job_url):
    def content_for_200(resp):
        if resp.code == 200:
            return resp.content()
        return defer.succeed(None)
    return jenkins_get(job_url + '/testReport/api/json').addCallback(content_for_200)
