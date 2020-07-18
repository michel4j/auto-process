Installation
============

It is recommended to install AutoProcess within a python virtual environment using setuptools.

.. code-block:: bash

    python3 -m venv venv
    source venv/bin/activate
    python setup.py install


This will install AutoProcess and it's dependences within the python environment. Once installed,
AutoProcess with be available for command line based data processing. See the doc:`process` section
for information help on how to use the individual commands.


Data Processing Server
======================
AutoProcess includes a built-in twisted server providing automated data processing from beamline data acquisition systems
such as MxDC.  The command to run the server is

.. code-block:: bash

    auto.server

However, it is preferable to start the server application from a systemd unit file or init script at startup to ensure
that the server is always available. An example unit file (`autoprocess.service`) is included in the top-level deploy directory of the archive.


.. py:currentmodule:: autoprocess.services.server

.. autoclass:: DPService
    :members:

.. py:currentmodule:: autoprocess.services.client

To use the server from an external python program, an example client class is provided in :class:`DPClient`. This client
code requires the use of a twisted reactor.

.. py:currentmodule:: autoprocess.services.client

.. autoclass:: DPClient
    :members:


Clusters
========
Installing AutoProcess in a cluster environment is recommended since XDS can run on multiple computers to
speed up the data processing. The following requirements should be satisfied in order to use AutoProcess on
multiple computers/nodes of a cluster.

1. SSH Key-Based Passwordless Authentication must be configured for each user wishing to use AutoProcess.
   If not already configured, it can be done using the following commands within a shell.


.. code-block:: bash

    ssh-keygen -t rsa -N "" -f ~/.ssh/id_rsa
    cat ~/.ssh/id_rsa.pub >> ~/.ssh/authorized_keys
    chmod 600 ~/.ssh/authorized_keys


2. The operating systems and all relevant libraries on all nodes should be ABI-compatible and preferably exactly the
   same version.
3. File access and the shell environments should be identical on all nodes. This can be accomplished through network
   file systems such as NFS.
4. Finally an environment variable `DPS_NODES` must be set which describes the cluster resources available.
   The format of the envronment variable takes the form of

.. code-block:: bash

    DPS_NODES="<host1-name>:<number of cores> <host2-name>:<number of cores> ..."

