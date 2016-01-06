# Copyright (c) ClusterHQ Ltd. See LICENSE for details.

import collections
import pandas


SUCCESS = u'SUCCESS'
FAILURE = u'FAILURE'


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
        }


def _flatten_builds(builds):
    for build in builds:
        for thing in _flatten_build(build):
            yield thing


def make_data_frame(builds):
    return pandas.DataFrame(_flatten_builds(builds))


def get_top_failing_jobs(build_data):
    failing_jobs = build_data[build_data['result'] == FAILURE]
    top_failing_jobs = failing_jobs.groupby('job').size()
    top_failing_jobs.sort(ascending=False)
    return top_failing_jobs
