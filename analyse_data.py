#!/usr/bin/env python

import json


from jenkins._jenkins import (
    BASE_DIR,
    make_data_frame,
    print_common_failure_reasons,
    print_commonly_failing_tests,
    print_summary_results,
    print_top_failing_jobs,
)


def load_build_data():
    info_files = BASE_DIR.globChildren('api.*.json')
    assert info_files, "Haven't downloaded any data"
    info_files.sort(key=lambda x: x.path)
    api_data = info_files[-1]
    with api_data.open() as f:
        return json.load(f)['builds']


def main():
    builds = load_build_data()
    print_summary_results(builds)
    build_data = make_data_frame(builds)
    print_top_failing_jobs(build_data)
    print_common_failure_reasons(build_data)
    print_commonly_failing_tests(build_data)


if __name__ == '__main__':
    main()
