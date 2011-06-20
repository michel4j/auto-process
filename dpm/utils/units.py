'''
Created on Jun 20, 2011

@author: michel
'''

import math

# Physical Constants
_h = 4.13566733e-15 # eV.s
_c = 299792458e10   # A/s


def energy_to_wavelength(energy): 
    """Convert energy in keV to wavelength in angstroms."""
    if energy == 0.0:
        return 0.0
    return (_h*_c)/(energy*1000.0)

def wavelength_to_energy(wavelength): 
    """Convert wavelength in angstroms to energy in keV."""
    if wavelength == 0.0:
        return 0.0
    return (_h*_c)/(wavelength*1000.0)

def air(e):
    p = [ 1.00000857e+00,  -3.10243288e-04,   3.01020914e+00]    
    return 1.0 - (p[0] * math.exp( p[1] * (e**p[2])))
