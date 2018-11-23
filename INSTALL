AutoProcess Installation
------------------------

1. Pre-requisites: See requirements.txt in the top level directory. It may work with earlier versions of the packages
   but those packages are needed for the full functionality.


    ** imageio package is needed if not included as part of the library. Should be in libs/imageio off the top-level
       directory.
    ** Crystallography packages
    - XDS (needs at least version 20170601)
    - Phenix (uses just xtriage)
    - CCP4 packages (especially POINTLESS and F2MTZ)
    - BEST (http://www.embl-hamburg.de/BEST/) (only needed for screening)
    - Fit2D (needed just for powder diffraction azimuthal integration, auto.powder)
    - CBFlib (needed in order to work with cbf formated files such as those produced by
      PILATUS)
 
2. Installation
    - unpack the tar archive in a directory of your choice such as 
      /usr/local/AutoProcess-XXXXXXXX or any folder of your choice. It doesn't matter.
    - edit the 'autoprocess.csh' and 'autoprocess.sh' files in the subfolder 'deploy' to match
      the installation. See the comments in those files.
    - copy those files to a location such that they are sourced at login, or 
      source them from your shell login scripts. At CMCF, they are in /cmcf_apps/profile.d,
      the same location as xds.sh, ccp4.sh best.sh, phenix_env.sh etc for setting up other
      crystallography packages to make sure all the required packages are in your path.
    - Setup ssh password-less login (http://www.linuxproblem.org/art_9.html) on 
      all machines you want to use as data processing slaves (including your 
      local machine), as configured in autoprocess.sh or autoprocess.csh. Adding more machines
      with multiple cores speeds up data processing. See the example for a 336 a core cluster.
    - Make sure the directories in which you'll be processing data from/in have
      exactly the same path on all machines configured (Use NFS). Also make sure
      all the machines are the same architecture and preferably the same 
      operating system version. You can not mix x86 and AMD64.
    - You can use a single machine to run AutoProcess but it might be very slow
      unless you have a lot of cores in it. If you want integration to happen 
      elsewhere while other tasks run locally, omit your local host from 
      autoprocess.csh & autoprocess.sh
    - To install the RPC server, copy "dpserver" file from the deploy subdirectory into
      the /etc/init.d directory of the server, modify the section at the top to make sure
      the environment is properly setup. Specifically change /cmcf_apps/profile.d to the location
      where all your xds, ccp4, phenix and autoprocess setup scripts are stored.  Add the script
      to the system (e.g systemctl enable dpserver ) and then start it (eg. systemctl start dpserver).
      Then update your MxDC configuration to point to the server. The dpserver runs on port 9991 by
      default.
    
3. Run AutoProcess
    - type 'auto.process -h' for help. You can also check our web site here 
      (http://cmcf.lightsource.ca/user-guide/autoprocess/) for more information. 
      Other tools available include auto.analyse, auto.inputs, auto.integrate, 
      auto.report, auto.scale, auto.strategy, auto.symmetry.
    - To be able to solve small molecule structures, you need to have SHELX and XPREP 
      installed.
      