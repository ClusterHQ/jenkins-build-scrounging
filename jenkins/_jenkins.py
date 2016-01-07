# Copyright (c) ClusterHQ Ltd. See LICENSE for details.

import collections
import pandas


SUCCESS = u'SUCCESS'
FAILURE = u'FAILURE'


import treq
from twisted.internet import defer
from twisted.internet import reactor

BASE_URL = 'http://ci-live.clusterhq.com:8080/'
BASE_PATH = 'job/ClusterHQ-flocker/job/master/job/__main_multijob/'
MAX_CONCURRENT_REQUESTS = 5


def jenkins_get(path):
    cookies = {'JSESSIONID.f304e28f': 'YOURCOOKIEHERE'}
    return treq.get(BASE_URL + path, cookies=cookies)


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


def extract_builds(resp):
    return resp['builds']

d = jenkins_json_get(BASE_PATH + 'api/json?tree=builds[result,number,subBuilds[result,buildNumber,jobName,url]]')
d.addCallback(extract_builds)


def get_build_result(build):
    """
    Aggregate all the results of the sub-builds of a build.
    """
    results = set(sub['result'] for sub in build['subBuilds'] if sub['result'])
    if results == set([SUCCESS]):
        return SUCCESS
    else:
        return FAILURE


def summarize_build_results(builds):
    return collections.Counter(map(get_build_result, builds))


def _flatten_build(build):
    for sub_build in build['subBuilds']:
        yield {
            'number': build['number'],
            'sub_number': sub_build['buildNumber'],
            'job': sub_build['jobName'],
            'result': sub_build['result'],
            'url': sub_build['url'],
        }


def _flatten_builds(builds):
    for build in builds:
        for thing in _flatten_build(build):
            yield thing


def make_data_frame(builds):
    frame = pandas.DataFrame(_flatten_builds(builds))
    frame.set_index(['url'])
    return frame


def get_top_failing_jobs(build_data):
    failing_jobs = build_data[build_data['result'] == FAILURE]
    top_failing_jobs = failing_jobs.groupby('job').size()
    return top_failing_jobs.sort_values(ascending=False)


def get_console_text(job_url):
    def content_for_200(resp):
        if resp.code == 200:
            return resp.content()
        return defer.succeed(None)
    return jenkins_get(job_url + '/consoleText').addCallback(content_for_200)


# XXX: Use t.p.constants
UNKNOWN = 0
NULLPOINTEREXCEPTION = 1
ARGPARSE130 = 2
TIMEOUT = 3
TESTTOOLS182 = 4
SLAVEOFFLINE = 5
DOCKER500 = 6
REMOVEOBSERVER = 7
MISSINGLOG = 8
GITCLEAN = 9

DESCRIPTIONS = {
    UNKNOWN: "Unknown",
    NULLPOINTEREXCEPTION: "[FLOC-3725] NullPointerException",
    ARGPARSE130: "[FLOC-?] PyPI down",
    TIMEOUT: "[FLOC-?] Build timeout",
    TESTTOOLS182: "[FLOC-?] testtools==1.8.2chq1 unavailable",
    SLAVEOFFLINE: "[FLOC-?] Slave went offline during the build",
    DOCKER500: "[FLOC-3077] docker.errors.APIError: 500 Server Error",
    REMOVEOBSERVER: "[FLOC-3681(fixed)] removeObserver on observer not in list",
    MISSINGLOG: "Missing log",
    GITCLEAN: "[FLOC-?] FATAL: Command 'git clean -fdx' returned status code 1",
}


def classify_build_log(log):
    if 'NullPointerException' in log:
        return DESCRIPTIONS[NULLPOINTEREXCEPTION]
    if 'No matching distribution found for argparse==1.3.0' in log:
        return DESCRIPTIONS[ARGPARSE130]
    if 'Build timed out' in log:
        return DESCRIPTIONS[TIMEOUT]
    if 'No matching distribution found for testtools==1.8.2chq1' in log:
        return DESCRIPTIONS[TESTTOOLS182]
    if 'Slave went offline during the build' in log:
        return DESCRIPTIONS[SLAVEOFFLINE]
    if 'error: flocker.node.functional.test_docker.NamespacedDockerClientTests.test_pull_image_if_necessary' in log and 'docker.errors.APIError: 500 Server Error: Internal Server Error ("Unknown device' in log:
        return DESCRIPTIONS[DOCKER500]
    if 'stderr:ValueError: list.remove(x): x not in list' in log:
        return DESCRIPTIONS[REMOVEOBSERVER]
    if 'FATAL: Command "git clean -fdx" returned status code 1:' in log:
        return DESCRIPTIONS[GITCLEAN]
    print "====="
    print "Unknown failure reason:"
    print "\n".join(log.splitlines()[-150:])
    print ""
    return DESCRIPTIONS[UNKNOWN]


def print_summary_results(builds):
    print "Top-level build results:"
    print summarize_build_results(builds)
    return builds

d.addCallback(print_summary_results)


def print_top_failing_jobs(builds):
    print ""
    print ""
    print "Jobs with the most failures"
    build_data = make_data_frame(builds)
    failing_jobs = get_top_failing_jobs(build_data)
    print failing_jobs.head(20)

    return build_data

d.addCallback(print_top_failing_jobs)


def print_common_failure_reasons(build_data):
    individual_failures = build_data[build_data['result'] == FAILURE]

    deferreds = []
    sem = defer.DeferredSemaphore(MAX_CONCURRENT_REQUESTS)
    for url in individual_failures['url']:
        d = sem.run(get_console_text, url)
        deferreds.append(d)

    dl = defer.DeferredList(deferreds)

    def classify_results(results):
        classifications = []
        for success, log in results:
            if success and log is not None:
                classifications.append(classify_build_log(log))
            else:
                classifications.append(DESCRIPTIONS[MISSINGLOG])
        return classifications

    def print_classification(classifications):
        individual_failures['classification'] = pandas.Series(classifications, index=individual_failures.index)
        print individual_failures.groupby('classification').size().sort_values(ascending=False)

    dl.addCallback(classify_results)
    dl.addCallback(print_classification)
    return dl


d.addCallback(print_common_failure_reasons)

def print_err(failure):
    print failure
    return failure

d.addErrback(print_err)

def cbShutdown(ignored):
        reactor.stop()

d.addBoth(cbShutdown)

reactor.run()
