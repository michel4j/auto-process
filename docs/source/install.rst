Installation
============

It is recommended to install AutoProcess within a python virtual environment using setuptools. Assuming you typically
install your applications in the directory `/MyApps`, you can install as follows

.. code-block:: bash

    cd /MyApps
    curl -s https://raw.githubusercontent.com/michel4j/auto-process/master/deploy/install.sh | bash


This is equivalent to running the following commands:

.. code-block:: bash

    cd /MyApps
    python3 -m venv auto-process
    source auto-process/bin/activate
    pip install --upgrade pip wheel
    pip install --upgrade mx-autoprocess


This will install AutoProcess and it's dependences within the the directory `/MyApps/auto-process`. Once installed,
AutoProcess with be available for command line based data processing. See the doc:`process` section
for information help on how to use the individual commands.


.. note::

    AutoProcess requires the following third-party packages to be properly installed and available in your path

    * XDS - http://xds.mpimf-heidelberg.mpg.de/html_doc/downloading.html
    * XDSSTAT - https://strucbio.biologie.uni-konstanz.de/xdswiki/index.php/Xdsstat
    * CCP4 - https://www.ccp4.ac.uk/
    * PHENIX - https://www.phenix-online.org/


To make the AutoProcess commands available within your shell, add `/MyApps/auto-process/bin` to your shell path.  The
following shell startup script could be used as an example:

.. code-block:: bash

    #! /usr/bin/bash

    # Format is "<host1-name>:<number of cores> <host2-name>:<number of cores> ..."
    export DPS_NODES="localhost:16"

    export DPS_PATH="/MyApps/auto-process"
    export PATH=${PATH}:$DPS_PATH/bin


Update the startup script to match your installation location. AutoProcess can submit jobs to other servers on your
local network for faster distributed processing.


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


Upgrading
=========
If a previous version of AutoProcess is already installed, then the following commands can be used to upgrade it to the latest
version.

.. code-block:: bash

    cd /MyApps
    curl -s https://raw.githubusercontent.com/michel4j/auto-process/master/deploy/upgrade.sh | bash

Which is equivalent to:

.. code-block:: bash

    cd /MyApps
    source auto-process/bin/activate
    pip install --upgrade pip wheel
    pip install --upgrade mx-autoprocess


Data Processing Server
======================
AutoProcess includes a built-in twisted server providing automated data processing from beamline data acquisition systems
such as MxDC.  The command to run the server is

.. code-block:: bash

    auto.server

However, it is preferable to start the server application from a systemd unit file or init script at startup to ensure
that the server is always available. An example unit file (`autoprocess.service`) is shown below:


.. code-block:: bash

    [Unit]
    Description=AutoProcess Server
    After=network.target network-online.target
    Wants=network-online.target

    [Service]
    User=root
    ExecStart=auto.server
    Restart=always

    [Install]
    WantedBy=multi-user.target


An example Init-Script for starting the AutoProcess Server is shown below:

.. code-block:: bash

    #!/bin/bash
    #
    # dpserver:   Data Processing Server
    #
    # chkconfig: 345 98 02
    # description:  This is a daemon listens for data processing commands and executes them \
    #               with the priviledges of the user requesting the action.
    #
    # Source function library.
    . /etc/rc.d/init.d/functions

    # Prepare environment by sourcing startup scripts for XDS, Phenix, CCP4 etc
    # update with 
    for profile in /MyApps/startup/*.sh; do
        if [ -r "$profile" ]; then
            source ${profile}
        fi
    done
    unset i

    # services parameters
    servicename='dpserver'
    pidfile='/var/run/dpserver.pid'
    logfile='/var/log/dpserver.log'
    appfile=/path/to/auto.tac
    umask=022

    export MPLCONFIGDIR=/tmp

    # Sanity checks.
    [ -f $appfile ] || exit 0

    start() {
        echo -n $"Starting Data Processing Server: "
        daemon /usr/bin/twistd -y $appfile --logfile=$logfile --umask=$umask --pidfile=$pidfile
        RETVAL=$?
        echo
        [ $RETVAL -eq 0 ] && touch /var/lock/subsys/$servicename
    }

    stop() {
        echo -n $"Stopping Data Processing Server: "

        killproc -p $pidfile
        RETVAL=$?
        echo
        if [ $RETVAL -eq 0 ]; then
            rm -f /var/lock/subsys/$servicename
            rm -f /var/run/$pidfile
        fi
    }

    # See how we were called.
    case "$1" in
        start)
            start
            ;;
        stop)
            stop
            ;;
        status)
            status -p $pidfile $servicename
            RETVAL=$?
            ;;
        restart)
            stop
        sleep 3
            start
            ;;
        condrestart)
            if [ -f /var/lock/subsys/$servicename ]; then
                stop
            sleep 3
                start
            fi
            ;;
        *)
            echo $"Usage: $0 {start|stop|status|restart|condrestart}"
            ;;
    esac
    exit $RETVAL


.. py:currentmodule:: autoprocess.services.server

.. autoclass:: DPService
    :members:

.. py:currentmodule:: autoprocess.services.client

To use the server from an external python program, an example client class is provided in :class:`DPClient`. This client
code requires the use of a twisted reactor.

.. py:currentmodule:: autoprocess.services.client

.. autoclass:: DPClient
    :members:


