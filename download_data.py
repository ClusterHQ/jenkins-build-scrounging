#!/usr/bin/env python


from __future__ import print_function

import datetime
from functools import partial
import json

from twisted.internet import defer
from twisted.internet.task import react

from jenkins._analysis import make_subbuild_data_frame
from jenkins._common import BASE_DIR, FAILURE, get_log_path
from jenkins._jenkins import (
    jenkins_json_get, get_console_text, MAX_CONCURRENT_REQUESTS,
    get_test_report,
)


def save_log(log, url):
    if log is not None:
        dir = get_log_path(url)
        if not dir.exists():
            dir.makedirs()
        f = dir.child('consoleText')
        f.setContent(log)


def save_test_report(data, url):
    if data is not None:
        dir = get_log_path(url)
        if not dir.exists():
            dir.makedirs()
        f = dir.child('testReport')
        f.setContent(data)


def fetch_failure_data(sem, url):
    d = sem.run(get_console_text, url)
    d.addCallback(lambda x: print(url) or x)
    d.addCallback(save_log, url)
    d.addCallback(lambda x: get_test_report(url))
    d.addCallback(save_test_report, url)
    return d


def main(reactor):
    if not BASE_DIR.exists():
        BASE_DIR.makedirs()
    base_path = 'job/ClusterHQ-flocker/job/master/job/__main_multijob/'
    d = jenkins_json_get(base_path + 'api/json?tree=builds[result,number,timestamp,subBuilds[result,buildNumber,jobName,url,timestamp]]')
    def write_main_data(data):
        filename = 'api.' + datetime.datetime.utcnow().isoformat() + '.json'
        json.dump(data, BASE_DIR.child(filename).open('wb'))
        return data
    d.addCallback(write_main_data)

    def download_failed_logs(data):
        builds = data['builds']
        build_data = make_subbuild_data_frame(builds)
        individual_failures = build_data[build_data['result'] == FAILURE]

        sem = defer.DeferredSemaphore(MAX_CONCURRENT_REQUESTS)
        deferreds = map(partial(fetch_failure_data, sem), individual_failures['url'])
        return defer.DeferredList(deferreds)

    d.addCallback(download_failed_logs)

    return d


if __name__ == '__main__':
    react(main)
