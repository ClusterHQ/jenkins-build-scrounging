Analyse Jenkins Failures
========================

Bootstrap
---------

   make boostrap
   . env/bin/activate

Download
--------

First you have to download the data. This will pull down all data for the last 100 builds of
master.

You will need the jenkins cookie for it to be able to download the data. Open your browser
and log in to http://ci-live.clusterhq.com:8080/. Then browse your cookies and find your
JSESSIONID cookie for that site. Copy the value and use it to run the script:

   JENKINS_AUTH_COOKIE=YOURCOOKIEHERE python download_data.py

(This uses JSESSIONID.f304e28f, I don't know if that is the same for everyone. If not
then hack jenkins/_jenkins.py and change the name, and let me know so I can parameterise
it.)

This will think for a while and suck down all the data needed to analyse the failures.


Analyse
-------

Now you can analyse the data by running

    python analyse_data.py


This will print output like:

    Top-level build results:
    Counter({u'FAILURE': 93, u'SUCCESS': 7})


    Jobs with the most failures
    job
    run_trial_for_ebs_storage_driver_on_Ubuntu_trusty_flocker_node_agents_ebs.py                 38
    run_acceptance_on_Rackspace_CentOS_7_for_flocker.acceptance.obsolete                         35
    run_trial_on_AWS_CentOS_7_flocker.node.functional.test_docker.NamespacedDockerClientTests    33
    run_acceptance_loopback_on_AWS_CentOS_7_for_flocker.acceptance                               31
    run_trial_for_cinder_storage_driver_on_CentOS_7_flocker_node_agents_cinder.py                31
    run_trial_on_AWS_CentOS_7_flocker.node.functional.test_docker.GenericDockerClientTests       29
    run_sphinx                                                                                   29
    run_acceptance_on_Rackspace_CentOS_7_for_flocker.acceptance.endtoend                         28
    run_trial_on_AWS_CentOS_7_flocker.restapi                                                    28
    run_acceptance_on_Rackspace_CentOS_7_for_flocker.acceptance.integration                      27
    run_trial_on_AWS_CentOS_7_flocker.common                                                     26
    run_acceptance_on_Rackspace_Ubuntu_Trusty_for_flocker.acceptance.obsolete                    24
    run_lint                                                                                     23
    run_acceptance_on_Rackspace_Ubuntu_Trusty_for_flocker.acceptance.endtoend                    22
    run_trial_on_AWS_CentOS_7_flocker.route                                                      22
    run_trial_for_cinder_storage_driver_on_Ubuntu_trusty_flocker_node_agents_cinder.py           20
    run_trial_for_ebs_storage_driver_on_CentOS_7_flocker_node_agents_ebs.py                      20
    run_client_installation_on_OSX                                                               19
    run_trial_on_AWS_CentOS_7_flocker.testtools                                                  19
    run_acceptance_on_AWS_CentOS_7_for_flocker.acceptance.obsolete                               19
    dtype: int64


    Missing log                                                        329
    [FLOC-?(fixed)] testtools==1.8.2chq1 unavailable                   329
    [FLOC-?] Jenkins slave communication failure                       220
    Failed Test                                                        129
    [FLOC-3725] NullPointerException                                   116
    [FLOC-?] Build timeout                                              69
    [FLOC-?] broken link in docs                                        23
    [FLOC-3681(fixed)] removeObserver on observer not in list           15
    [FLOC-?] FATAL: Command 'git clean -fdx' returned status code 1     11
    [FLOC-?] virtualbox failure                                          8
    [FLOC-?] failure download virtualbox box                             8
    [FLOC-?] RequestLimitExceeded                                        6
    [FLOC-?] apt download failure                                        3
    [FLOC-?] PyPI down                                                   2
    [FLOC-?] rackspace node failed to start in time                      1
    [FLOC-?] docker daemon not running                                   1
    [FLOC-?] failed to find key on keyserver                             1
    [FLOC-?] failed to get availability zone info                        1
    [FLOC-?] failed to get key from keyserver                            1
    Lint failures                                                        1
    dtype: int64

You can see that there was a 7% success rate for the whole build on master, and that
run_trial_for_ebs_storage_driver_on_Ubuntu_trusty_flocker_node_agents_ebs.py failed
the most often.

There's also an attempt to categorise the specific failures in to buckets. It could
use some work.

It may also print some build logs, this would happen if there was a failure that
it couldn't categorise.
