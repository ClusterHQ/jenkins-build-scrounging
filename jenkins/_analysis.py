# Copyright (c) ClusterHQ Ltd. See LICENSE for details.

import collections
import datetime
import json

import numpy
import pandas


from ._common import (
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


def _parse_duration(duration):
    """
    Parses a duration from jenkins into a python timedelta. Note that jenkins
    gives durations in two different forms. Sometimes durations are specified
    in a human-readable-ish format like "12 hr 20 min 14 sec", and sometimes it
    is specified as an integer of milliseconds. This function handles both.

    :param unicode duration: A duration from jenkins.
    :returns: A python timedelta representing the duration.
    """
    if type(duration) == int:
        return datetime.timedelta(milliseconds=duration)

    result = datetime.timedelta()
    remainder = duration

    # Be sure to order the following from largest to smallest. Jenkins orders
    # them from largest to smallest similar to natural language.
    for jenkins_keyword, timedelta_kwarg in [
        ('hr', 'hours'),
        ('min', 'minutes'),
        ('sec', 'seconds')
    ]:
        if jenkins_keyword in remainder:
            value, remainder = remainder.split(jenkins_keyword)
            result += datetime.timedelta(**{timedelta_kwarg: float(value)})
    return result


def _flatten_build(build):
    for sub_build in build['subBuilds']:
        yield {
            'number': build['number'],
            'sub_number': sub_build['buildNumber'],
            'job': sub_build['jobName'],
            'result': sub_build['result'],
            'url': sub_build['url'],
            'datetime': get_datetime(build['timestamp']),
            'sub_duration': _parse_duration(sub_build['duration']),
            'duration': _parse_duration(build['duration'])
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
    if 'java.io.IOException: remote file operation failed:' in log:
        return '[FLOC-4172] java.io.IOException: remote file operation failed'
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
    if 'upload failed: ' in log and 'Unable to parse response ' in log and ' invalid XML received:' in log:
        return "[FLOC-?] docs failed to upload to s3"
    if 'git fetch --tags --progress https://github.com/ClusterHQ/flocker.git +refs/heads/*:refs/remotes/upstream/*\nERROR: timeout after 10 minutes' in log:
        return "[FLOC-?] failed to fetch from github"
    if ("ReadTimeoutError: HTTPConnectionPool(host='devpi.clusterhq.com', "
            "port=3141): Read timed out." in log):
        return "[FLOC-?] devpi.clusterhq.com down"
    if ("No matching distribution found for effect==0.1a13 "
            "(from -r /tmp/requirements.txt (line 6))" in log):
        return "[FLOC-?] Pip failure in docker build."
    if ("Could not resolve host: github.com" in log or
            "curl: (6) Could not resolve host: api.github.com" in log):
        return "[FLOC-?] Network to github down."

    # XXX: overly hacky and broad. Not caught by either the junit processing
    # check due to FLOC-3817, or by the trial failure message check because it is showing
    # the subunit
    if '\nerror: flocker.' in log:
        return "Failed Test"
    print "Unknown failure reason:", path.path
    return "Unknown"


def get_datetime(timestamp):
    """
    Return the datetime from a jenkins timestamp.

    :param int timestamp: The timestamp to convert in ms since utc
        to a datetime
    :return datetime: The corresponding datetime.
    """
    return datetime.datetime.fromtimestamp(float(timestamp)/1000)


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
    dt = get_datetime(timestamp)
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
        path = get_log_path(url).child('testReport')
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


def get_time_to_success(build_data):
    """
    Attempts to approximate how much time it would take each of the sub-builds
    to reach an outcome conducive with merging a PR. This is an approximation
    from the time that __main_multijob is originally pressed, until the
    sub-build has been successfully concluded after retries.

    As a baseline we take the duration of __main_multijob. An engineer should
    not merge a branch in ideal conditions until __main_multijob is concluded.

    If a job fails, we add to the time of __main_multijob the amount of time of
    the next run of the same job. In the worst case a job fails and it was the
    last job to run in __main_multijob. This approximates immediately hitting
    retry on the failed job in that scenario. This is repeated until we get a
    to a successful run of the job.

    Note that if the most recent job is a failure, then this column will have
    NaT in this column.

    :param build_data: A DataFrame representing the individual builds of the
        test jobs.
    :returns: A DataFrame that has all of the original columns plus an
        additional column named "duration_until_mergable" that contains the
        amount of time from the start of __main_multijob until this sub-build
        has been retried until success, assuming this was the final job in the
        __main_multijob build.
    """
    grouped = build_data.groupby('job')
    new_columns = None
    for name, group in grouped:
        last = None
        group_rows = []
        for row in group.sort_values(by='datetime',
                                     ascending=False).itertuples():
            new = {
                "index": row.Index,
                "time_to_success": row.sub_duration,
                "duration_until_mergable": row.duration
            }
            if row.result != SUCCESS:
                if last:
                    new['time_to_success'] += last["time_to_success"]
                    new['duration_until_mergable'] += (
                        last["time_to_success"])
                else:
                    new['time_to_success'] = numpy.nan
                    new['duration_until_mergable'] = numpy.nan
            last = new
            group_rows.append(new)
        new_rows = pandas.DataFrame.from_records(
            group_rows, index=['index'], exclude=['time_to_success'])
        if new_columns is None:
            new_columns = new_rows
        else:
            new_columns = new_columns.append(new_rows)
    result = build_data.join(new_columns)
    return result


def get_daily_time_to_merge(build_data):
    """
    Construct a DataFrame that returns a per-day approximation of the amount of
    time between CI starting and all builds going green. This is an attempt at
    approximating time to merge.

    :param build_data: A DataFrame with the per-subbuild information.
    :returns: A DataFrame with one row for each day the data occurred during,
        and has values that are the average approximated time to submit for
        that day.
    """
    build_data_with_durations = get_time_to_success(build_data)

    def max_preserving_NaTs(x):
        if any(x.isnull()):
            return pandas.NaT
        return numpy.max(x)

    per_build_durations = (
        build_data_with_durations[['number',
                                   'datetime',
                                   'duration_until_mergable']]
        .groupby('number')
        .aggregate(max_preserving_NaTs))

    def avg_perserving_NaTs(x):
        if len(x) == 0:
            return "No data"
        if any(x.isnull()):
            return pandas.NaT
        return numpy.mean(x)

    return per_build_durations.groupby(
            pandas.Grouper(key='datetime', freq='D', sort=True),
    )['duration_until_mergable'].aggregate(avg_perserving_NaTs)


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


def get_daily_classification_pivot(failures):
    """
    Given a DataFrame of classified failures, group the frame by classification
    and day to produce a table that shows the daily occurances of each of the
    types of failures.

    :param pandas.DataFrame failures: the DataFrame with classified failures.
    :return pandas.DataFrame: A pandas.DataFrame pivot table with rows for each
        type of failure and columns for each day of data. This can be scanned
        to see if a failure has gone away, or has re-emerged in recent days.
    """
    return pandas.pivot_table(
        failures,
        index='classification',
        columns=pandas.Grouper(key='datetime', freq='D', sort=True),
        values='url',
        aggfunc='count',
        fill_value=0
    )


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

