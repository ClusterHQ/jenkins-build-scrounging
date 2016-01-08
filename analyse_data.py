#!/usr/bin/env python

from argparse import ArgumentParser
from datetime import datetime
import json

import dateutil


from jenkins._jenkins import (
    BASE_DIR,
    make_data_frame,
    print_common_failure_reasons,
    print_commonly_failing_tests,
    print_summary_results,
    print_top_failing_jobs,
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
        lambda b: datetime.fromtimestamp(float(b['timestamp'])/1000) > since,
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
    print_summary_results(builds)
    build_data = make_data_frame(builds)
    print_top_failing_jobs(build_data)
    print_common_failure_reasons(build_data)
    print_commonly_failing_tests(build_data)


if __name__ == '__main__':
    main()
