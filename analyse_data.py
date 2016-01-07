#!/usr/bin/env python

import json


from jenkins._jenkins import (
    BASE_DIR,
    make_data_frame,
    print_common_failure_reasons,
    print_summary_results,
    print_top_failing_jobs,
)


def load_build_data():
    api_data = BASE_DIR.child('api.json')
    with api_data.open() as f:
        return json.load(f)['builds']


def main():
    builds = load_build_data()
    print_summary_results(builds)
    build_data = make_data_frame(builds)
    print_top_failing_jobs(build_data)
    print_common_failure_reasons(build_data)


if __name__ == '__main__':
    main()
