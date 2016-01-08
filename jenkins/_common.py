# Copyright (c) ClusterHQ Ltd. See LICENSE for details.

from twisted.python.filepath import FilePath


BASE_DIR = FilePath('data/')

SUCCESS = u'SUCCESS'
FAILURE = u'FAILURE'
PASSED = u'PASSED'
SKIPPED = u'SKIPPED'
FIXED = u'FIXED'


def _child_of(file_path, url_path):
    """Return a descendant of file_path."""
    return file_path.preauthChild(url_path)


def get_log_path(url):
    """
    Get the directory containing the info files for url.

    :param str url: a partial url that identifies a build.
    :return FilePath: the file path corresponding to a directory that
        may have the log files for that build.
    """
    return _child_of(BASE_DIR.child('logs'), url)
