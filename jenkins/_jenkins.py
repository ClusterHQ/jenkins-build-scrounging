# Copyright (c) ClusterHQ Ltd. See LICENSE for details.

import collections
import json
import os
import pandas


SUCCESS = u'SUCCESS'
FAILURE = u'FAILURE'
PASSED = u'PASSED'
SKIPPED = u'SKIPPED'
FIXED = u'FIXED'


import treq
from twisted.internet import defer
from twisted.python.filepath import FilePath

BASE_URL = 'http://ci-live.clusterhq.com:8080/'

PASSWORD_ENV_VAR = 'JENKINS_PASSWORD'

BASE_DIR = FilePath('data/')


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


def extract_builds(resp):
    return resp['builds']


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


def get_test_report(job_url):
    def content_for_200(resp):
        if resp.code == 200:
            return resp.content()
        return defer.succeed(None)
    return jenkins_get(
        job_url + '/testReport/api/json').addCallback(content_for_200)


def classify_build_log(log, path):
    if 'NullPointerException' in log:
        return "[FLOC-3725] NullPointerException"
    if 'No matching distribution found for argparse==1.3.0' in log or 'pkg_resources.DistributionNotFound: The \'docutils>=0.10\'' in log:
        return "[FLOC-?] PyPI down"
    if 'Build timed out' in log:
        return "[FLOC-?] Build timeout"
    if 'No matching distribution found for testtools==1.8.2chq1' in log:
        return "[FLOC-?(fixed)] testtools==1.8.2chq1 unavailable"
    if 'Slave went offline during the build' in log:
        return "[FLOC-?] Slave went offline during the build"
    if 'stderr:ValueError: list.remove(x): x not in list' in log:
        return "[FLOC-3681(fixed)] removeObserver on observer not in list"
    if 'FATAL: Command "git clean -fdx" returned status code 1:' in log:
        return "[FLOC-?] FATAL: Command 'git clean -fdx' returned status code 1"
    if 'hudson.remoting.RequestAbortedException' in log or 'org.jenkinsci.lib.envinject.EnvInjectException' in log or 'java.lang.IllegalStateException' in log:
        return "[FLOC-?] Jenkins slave communication failure"
    if 'run_sphinx' in path.path and ' broken ' in log:
        return "[FLOC-?] broken link in docs"
    if 'Connection to 127.0.0.1 closed by remote host.' in log:
        return "[FLOC-?] virtualbox failure"
    if 'acceptance' in path.path and 'FAILED (' in log:
        return "Failed Test"
    if 'E: Some index files failed to download.' in log:
        return "[FLOC-?] apt download failure"
    if 'FLOCKER_FUNCTIONAL_TEST_AWS_AVAILABILITY_ZONE=\nBuild step \'Execute shell\' marked build as failure' in log:
        return "[FLOC-?] failed to get availability zone info"
    if 'ERROR:   lint: commands failed' in log:
        return "Lint failures"
    if 'The box failed to unpackage properly.' in log:
        return "[FLOC-?] failure download virtualbox box"
    if 'Cannot connect to the Docker daemon. Is the docker daemon running on this host?' in log:
        return "[FLOC-?] docker daemon not running"
    if 'boto.exception.BotoServerError: BotoServerError: 503 Service Unavailable' in log and 'RequestLimitExceeded' in log:
        return "[FLOC-?] RequestLimitExceeded"
    if 'LoopExceeded' in log and 'create_node' in log and 'rackspace' in log:
        return "[FLOC-?] rackspace node failed to start in time"
    if 'gpg: keyserver receive failed: keyserver error' in log:
        return "[FLOC-?] failed to get key from keyserver"
    if 'gpgkeys: key 58118E89F3A912897C070ADBF76221572C52609D not found on keyserver' in log:
        return "[FLOC-?] failed to find key on keyserver"

    # XXX: overly hacky and broad. Not caught by either the junit processing
    # check due to FLOC-3817, or by the trial failure message check because it
    # is showing the subunit
    if '\nerror: flocker.' in log:
        return "Failed Test"
    print "====="
    print "Unknown failure reason:"
    print path.path
    print "\n".join(log.splitlines())
    print ""
    return "Unknown"


def print_summary_results(builds):
    print "Top-level build results:"
    print summarize_build_results(builds)


def print_top_failing_jobs(build_data):
    print ""
    print ""
    print "Jobs with the most failures"
    failing_jobs = get_top_failing_jobs(build_data)
    print failing_jobs.head(20)


def child_of(file_path, url_path):
    """Return a descendant of file_path."""
    result = file_path
    for segment in url_path.split('/'):
        result = result.child(segment)
    return result


def print_common_failure_reasons(build_data):
    individual_failures = build_data[build_data['result'] == FAILURE]

    classifications = []
    for url in individual_failures['url']:
        path = child_of(BASE_DIR.child('logs'), url).child('testReport')
        if path.exists():
            classifications.append("Failed Test")
        else:
            path = child_of(BASE_DIR.child('logs'), url).child('consoleText')
            if path.exists():
                with path.open() as f:
                    classifications.append(classify_build_log(f.read(), path))
            else:
                classifications.append("Missing log")

    individual_failures['classification'] = pandas.Series(
        classifications, index=individual_failures.index)
    print ""
    print ""
    print "Classification of failures"
    print individual_failures.groupby('classification').size().sort_values(
        ascending=False)


def test_case_name(case):
    return case['className'] + '.' + case['name']


def test_case_failed(case):
    return case['status'] not in (SKIPPED, PASSED, FIXED)


def list_tests(test_report):
    for suite in test_report['suites']:
        for case in suite['cases']:
            yield case


def get_failing_tests(test_report):
    return list(filter(test_case_failed, list_tests(test_report)))


def print_commonly_failing_tests(build_data):
    individual_failures = build_data[build_data['result'] == FAILURE]

    failing_cases = []
    for url in individual_failures['url']:
        path = child_of(BASE_DIR.child('logs'), url).child('testReport')
        if path.exists():
            with path.open() as f:
                tests = json.load(f)
                failing_cases.extend(get_failing_tests(tests))

    failing_frame = pandas.DataFrame(failing_cases)
    failing_frame['test_case_name'] = (
        failing_frame['className'] + '.' + failing_frame['name'])
    print ""
    print ""
    print "Tests with the most failures"
    print failing_frame.groupby('test_case_name').size().sort_values(
        ascending=False).head(20)
