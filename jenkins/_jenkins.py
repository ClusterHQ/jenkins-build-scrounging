# Copyright (c) ClusterHQ Ltd. See LICENSE for details.

import collections
import pandas


SUCCESS = u'SUCCESS'
FAILURE = u'FAILURE'


import requests
BASE_URL = 'http://ci-live.clusterhq.com:8080/'
BASE_PATH = 'job/ClusterHQ-flocker/job/master/job/__main_multijob/'


def jenkins_get(path):
    cookies = {'JSESSIONID.f304e28f': 'YOURCOOKIEHERE'}
    return requests.get(BASE_URL + path, cookies=cookies)


def jenkins_json_get(path):
    return jenkins_get(path).json()


builds = jenkins_json_get(BASE_PATH + 'api/json?tree=builds[result,number,subBuilds[result,buildNumber,jobName,url]]')['builds']


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
    return jenkins_get(url + '/consoleText').content


# XXX: Use t.p.constants
UNKNOWN = 0
NULLPOINTEREXCEPTION = 1


def classify_build_log(log):
    if 'NullPointerException' in log:
        return NULLPOINTEREXCEPTION
    return UNKNOWN


print "Top-level build results:"
print summarize_build_results(builds)
print ""
print ""
print "Jobs with the most failures"
build_data = make_data_frame(builds)
failing_jobs = get_top_failing_jobs(build_data)
print failing_jobs.head(20)


top_job = failing_jobs.index[0]

individual_failures = build_data[build_data['result'] == FAILURE]

classifications = []
for url in individual_failures['url']:
    classifications.append(classify_build_log(get_console_text(url)))

individual_failures['classification'] = pandas.Series(classifications, index=individual_failures.index)
print individual_failures.groupby('classification').size().sort_values(ascending=False)
