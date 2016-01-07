#!/usr/bin/env python


from __future__ import print_function

from functools import partial
import json

from twisted.internet import defer
from twisted.internet.task import react
from twisted.python.filepath import FilePath

from jenkins._jenkins import jenkins_json_get, make_data_frame, get_console_text, MAX_CONCURRENT_REQUESTS, FAILURE


BASE_DIR = FilePath('data/')


def child_of(file_path, url_path):
    """Return a descendant of file_path."""
    result = file_path
    for segment in url_path.split('/'):
        result = result.child(segment)
    return result


def save_log(log, url):
    if log is not None:
        dir = child_of(BASE_DIR.child('logs'), url)
        if not dir.exists():
            dir.makedirs()
        print(dir)
        f = dir.child('consoleText')
        f.setContent(log)


def fetch_console_text(sem, url):
    d = sem.run(get_console_text, url)
    d.addCallback(lambda x: print(url) or x)
    d.addCallback(save_log, url)
    return d


def main(reactor):
    if not BASE_DIR.exists():
        BASE_DIR.makedirs()
    base_path = 'job/ClusterHQ-flocker/job/master/job/__main_multijob/'
    d = jenkins_json_get(base_path + 'api/json?tree=builds[result,number,subBuilds[result,buildNumber,jobName,url]]')
    def write_main_data(data):
        json.dump(data, BASE_DIR.child('api.json').open('wb'))
        return data
    d.addCallback(write_main_data)

    def download_failed_logs(data):
        builds = data['builds']
        build_data = make_data_frame(builds)
        individual_failures = build_data[build_data['result'] == FAILURE]

        sem = defer.DeferredSemaphore(MAX_CONCURRENT_REQUESTS)
        deferreds = map(partial(fetch_console_text, sem), individual_failures['url'])
        return defer.DeferredList(deferreds)

    d.addCallback(download_failed_logs)

    return d


if __name__ == '__main__':
    react(main)
