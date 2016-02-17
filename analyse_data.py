#!/usr/bin/env python

from __future__ import print_function

from argparse import ArgumentParser
import json

import dateutil
import pandas
import numpy

from jenkins._common import BASE_DIR
from jenkins._analysis import (
    analyze_failing_tests,
    get_daily_time_to_merge,
    get_datetime,
    get_classified_failures,
    get_daily_classification_pivot,
    get_top_failing_jobs,
    group_by_classification,
    group_by_test_name,
    make_build_data_frame,
    make_subbuild_data_frame,
    summarize_build_results,
    summarize_weekly_stats,
)


def builds_since(builds, since):
    """
    Filter a list of builds to only those newer than the
    provided timestamp.

    :param Iterable[dict]: an iterable of dicts of build
        data.
    :param datetime since: exclude any build
        records before this datetime.
    :return Iterable[dict]: an iterable containing only the
        records in `builds` that are newer than `since`.
    """
    return filter(
        lambda b: get_datetime(b['timestamp']) > since,
        builds)


def load_build_data(since=None):
    """
    Load the build data.

    :param Optional[datetime] since: only builds newer than this datetime
           will be included if this is provided.
    :return Iterable[dict]: an iterable of build records.
    """
    info_files = BASE_DIR.globChildren('api.*.json')
    assert info_files, "Haven't downloaded any data"
    info_files.sort(key=lambda x: x.path)
    api_data = info_files[-1]
    with api_data.open() as f:
        builds = json.load(f)['builds']
        if since:
            builds = builds_since(builds, since)
        return builds


def print_summary_results(builds):
    print("Top-level build results:")
    print(summarize_build_results(builds))
    print("")
    print("")
    print("Success percentage by week")
    print(summarize_weekly_stats(make_build_data_frame(builds)))


def print_top_failing_jobs(build_data):
    print("Jobs with the most failures")
    failing_jobs = get_top_failing_jobs(build_data)
    print(failing_jobs.head(20))


def print_common_failure_reasons(classified_failure_data):
    print("Classification of failures")
    print(group_by_classification(classified_failure_data))


def print_common_failure_daily(classified_failure_data):
    print("Daily drill-down on failure classifications:")
    print(get_daily_classification_pivot(classified_failure_data))


def print_commonly_failing_tests(build_data):
    print("Tests with the most failures")
    print(group_by_test_name(analyze_failing_tests(build_data)).head(20))


def print_daily_time_to_merge(build_data):
    print("Approximation of time-to-merge across days:")
    print(get_daily_time_to_merge(build_data))


def main():
    parser = ArgumentParser(
        'analyse_data.py', description="Analyze Jenkins build logs"
    )
    parser.add_argument(
        '--since', type=dateutil.parser.parse,
        help="Only consider builds since this date"
    )
    opts = parser.parse_args()
    builds = load_build_data(since=opts.since)

    pandas.set_option('expand_frame_repr', False)
    print("Showing data since: ", opts.since)
    print("")
    print_summary_results(builds)
    print("")
    print("")
    build_data = make_subbuild_data_frame(builds)
    print_top_failing_jobs(build_data)
    print("")
    print("")
    classified_failure_data = get_classified_failures(build_data)
    print_common_failure_reasons(classified_failure_data)
    print("")
    print("")
    print_common_failure_daily(classified_failure_data)
    print("")
    print("")
    print_commonly_failing_tests(build_data)
    print("")
    print("")
    print_daily_time_to_merge(build_data)


if __name__ == '__main__':
    main()
