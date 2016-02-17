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
    jenkins_json_get, get_console_text, get_test_report,
)


MAX_CONCURRENT_REQUESTS = 10


def save_log(log, url):
    if log is None:
        return
    dir = get_log_path(url)
    if not dir.exists():
        dir.makedirs()
    f = dir.child('consoleText')
    f.setContent(log)


def save_test_report(data, url):
    # XXX: Duplication w/ save_log
    if data is None:
        return
    dir = get_log_path(url)
    if not dir.exists():
        dir.makedirs()
    f = dir.child('testReport')
    f.setContent(data)


def fetch_failure_data(sem, url):
    console = sem.run(get_console_text, url)
    console.addCallback(lambda x: print(url) or x)
    console.addCallback(save_log, url)

    test = sem.run(get_test_report, url)
    test.addCallback(save_test_report, url)

    return defer.gatherResults([console, test])


def _get_failure_urls(api_json_data):
    """
    Given Jenkins data for a build, return the URLs of the failed sub-builds.
    """
    builds = api_json_data['builds']
    build_data = make_subbuild_data_frame(builds)
    individual_failures = build_data[build_data['result'] == FAILURE]
    return individual_failures['url']


def main(reactor):
    if not BASE_DIR.exists():
        BASE_DIR.makedirs()
    base_path = 'job/ClusterHQ-flocker/job/master/job/__main_multijob/'
    d = jenkins_json_get(
        base_path + 'api/json?tree=builds[result,number,timestamp,duration,'
        'subBuilds[result,buildNumber,jobName,url,timestamp,duration]]')

    def write_main_data(data):
        filename = 'api.' + datetime.datetime.utcnow().isoformat() + '.json'
        json.dump(data, BASE_DIR.child(filename).open('wb'))
        return data
    d.addCallback(write_main_data)

    d.addCallback(_get_failure_urls)

    def download_failed_logs(urls):
        sem = defer.DeferredSemaphore(MAX_CONCURRENT_REQUESTS)
        deferreds = map(partial(fetch_failure_data, sem), urls)
        return defer.DeferredList(deferreds)

    d.addCallback(download_failed_logs)
    return d


if __name__ == '__main__':
    react(main)
