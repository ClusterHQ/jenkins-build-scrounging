# Copyright (c) ClusterHQ Ltd. See LICENSE for details.

import collections
import datetime
import json

import numpy
import pandas


from ._common import (
    BASE_DIR,
    SUCCESS,
    FAILURE,
    PASSED,
    SKIPPED,
    FIXED,
    get_log_path,
)


def _get_build_result(build):
    """
    Aggregate all the results of the sub-builds of a build.
    """
    results = set(sub['result'] for sub in build['subBuilds'] if sub['result'])
    if results == set([SUCCESS]):
        return SUCCESS
    else:
        return FAILURE


def summarize_build_results(builds):
    return collections.Counter(map(_get_build_result, builds))


def summarize_weekly_stats(builds):
    """
    Summarize the per-week data

    :param Iterable[dict] builds: An iterable of build
        data dicts.
    :return pandas.DataFrameGroupBy: a data frame
        grouped by week_number, with summary information
        for each week.
    """
    df = make_build_data_frame(builds)
    return df.groupby('week_number').agg(
        {'numeric_result': {
            'test runs': lambda x: x.count(),
            'success percentage': numpy.mean
        }}
    )['numeric_result']


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


def make_build_data_frame(builds):
    """
    Make a DataFrame from of top-level build information.

    :param Iterable[dict] builds: an iterable of
        dicts of build information.
    :return pandas.DataFrame: a DataFrame containing
        that data augmented with week number
        and numeric result.
    """
    return pandas.DataFrame(builds).assign(
        week_number=_make_week_numbers,
        numeric_result=_make_numeric_results,
    )


def make_subbuild_data_frame(builds):
    """
    Make a DataFrame from of sub build information.

    This indexes all builds that are triggered by
    the top level builds.

    :param Iterable[dict] builds: an iterable of
        dicts of build information.
    :return pandas.DataFrame: a DataFrame containing
        that data.
    """
    frame = pandas.DataFrame(_flatten_builds(builds))
    frame.set_index(['url'])
    return frame


def get_top_failing_jobs(build_data):
    failing_jobs = build_data[build_data['result'] == FAILURE]
    top_failing_jobs = failing_jobs.groupby('job').size()
    return top_failing_jobs.sort_values(ascending=False)


def _classify_build_log(log, path):
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
    # check due to FLOC-3817, or by the trial failure message check because it is showing
    # the subunit
    if '\nerror: flocker.' in log:
        return "Failed Test"
    print "====="
    print "Unknown failure reason:"
    print path.path
    print "\n".join(log.splitlines())
    print ""
    return "Unknown"


def _get_week_number(timestamp):
    """
    Return a week number for the timestamp.

    This combines the year and the week number so that
    it can handle per-week processing of data that
    spans multiple years.

    :param datetime timestamp: The timestamp to convert
        to a week number.
    :return int: the week number.
    """
    dt = datetime.datetime.fromtimestamp(float(timestamp)/1000)
    return dt.year * 100 + dt.isocalendar()[1]


def _get_numeric_result(result_str):
    """
    Convert a test result status in to a number.

    :param str result_str: test result status
        ("SUCCESS", "FAILED", etc.)
    :return int: 100 if the test passed, 0 if it
        failed. These mean of these values will
        be the percentage of successful tests.
    """
    if result_str == SUCCESS:
        return 100
    return 0


def _make_numeric_results(builds):
    return builds['result'].map(_get_numeric_result)


def _make_week_numbers(builds):
    return builds['timestamp'].map(_get_week_number)


def _classify(url):
    """
    Classify the failure of a url.

    Considers all the information about the url, such as testReport
    consoleText and tries to provide the best classification.

    :param str url: a url of a build.
    :return str: the classification.
    """
    path = get_log_path(url).child('testReport')
    if path.exists():
        return "Failed Test"
    else:
        path = get_log_path(url).child('consoleText')
        if path.exists():
            with path.open() as f:
                return _classify_build_log(f.read(), path)
        else:
            return "Missing log"


def _test_case_name(case):
    return case['className'] + '.' + case['name']


def _test_case_failed(case):
    return case['status'] not in (SKIPPED, PASSED, FIXED)


def _list_tests(test_report):
    for suite in test_report['suites']:
        for case in suite['cases']:
            yield case


def _get_failing_tests(test_report):
    return list(filter(_test_case_failed, _list_tests(test_report)))


def analyze_failing_tests(build_data):
    """
    Given a DataFrame of build data, analyse which
    individaul tests are failing the builds.

    :param pandas.DataFrame build_data: the build data to
        analyze.
    :return pandas.DataFrame: a new DataFrame with
        information about individual failing tests.
    """
    individual_failures = build_data[build_data['result'] == FAILURE]

    failing_cases = []
    for url in individual_failures['url']:
        path = child_of(BASE_DIR.child('logs'), url).child('testReport')
        if path.exists():
            with path.open() as f:
                tests = json.load(f)
                failing_cases.extend(_get_failing_tests(tests))

    failing_frame = pandas.DataFrame(failing_cases)
    return failing_frame.assign(test_case_name=_test_case_name)


def get_classified_failures(build_data):
    """
    Given a DataFrame of build data, guess what caused
    each failure. Return a DataFrame including a new
    column: a string that describes the best guess
    of the cause of that failure.

    :param pandas.DataFrame build_data: a DataFrame with
        information about jobs.
    :return pandas.DataFrame: a new DataFrame with a row
        for each failing build in the input frame, and
        an additional column describing the failure reason.
    """
    individual_failures = build_data[build_data['result'] == FAILURE]

    classifications = individual_failures['url'].map(_classify)
    individual_failures.insert(3, 'classification', classifications)
    return individual_failures


def group_by_classification(failures):
    """
    Given a DataFrame of classified failures, group
    the frame by classification and sort with the
    most common first.

    :param pandas.DataFrame failures: the DataFrame
        with classified failures.
    :return pandas.DataFrameGroupBy: a grouped DataFrame
        with the most common classifications first and
        a column with the frequency.
    """
    return failures.groupby('classification').size().sort_values(
        ascending=False)


def group_by_test_name(failures):
    """
    Given a DataFrame of failing tests group the
    frame by the test name and sort with the most
    common first.

    :param pandas.DataFrame failures: the DataFrame
        with failing tests.
    :return pandas.DataFrameGroupBy: a grouped DataFrame
        with the most common failing tests first and
        a column with the frequency.
    """
    return failures.groupby('test_case_name').size().sort_values(
        ascending=False)

