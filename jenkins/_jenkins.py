# Copyright (c) ClusterHQ Ltd. See LICENSE for details.

import collections


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
