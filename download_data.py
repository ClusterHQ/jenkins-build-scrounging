#!/usr/bin/env python


from __future__ import print_function

from functools import partial
import json

from twisted.internet import defer
from twisted.internet.task import react

from jenkins._jenkins import (
    jenkins_json_get, make_data_frame, get_console_text,
    MAX_CONCURRENT_REQUESTS, FAILURE, BASE_DIR,
    child_of, get_test_report,
)


def save_log(log, url):
    if log is None:
        return
    dir = child_of(BASE_DIR.child('logs'), url)
    if not dir.exists():
        dir.makedirs()
    f = dir.child('consoleText')
    f.setContent(log)


def save_test_report(data, url):
    if data is not None:
        dir = child_of(BASE_DIR.child('logs'), url)
        if not dir.exists():
            dir.makedirs()
        f = dir.child('testReport')
        f.setContent(data)


def fetch_failure_data(sem, url):
    d = sem.run(get_console_text, url)
    d.addCallback(lambda x: print(url) or x)
    d.addCallback(save_log, url)
    d.addCallback(lambda ignored: get_test_report(url))
    d.addCallback(save_test_report, url)
    return d


def _get_failure_urls(api_json_data):
    """
    Given Jenkins data for a build, return the URLs of the failed sub-builds.
    """
    builds = api_json_data['builds']
    build_data = make_data_frame(builds)
    individual_failures = build_data[build_data['result'] == FAILURE]
    return individual_failures['url']


def main(reactor):
    if not BASE_DIR.exists():
        BASE_DIR.makedirs()
    base_path = 'job/ClusterHQ-flocker/job/master/job/__main_multijob/'
    d = jenkins_json_get(
        base_path + 'api/json?tree=builds[result,number,subBuilds'
        '[result,buildNumber,jobName,url]]')

    def write_main_data(data):
        json.dump(data, BASE_DIR.child('api.json').open('wb'))
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
