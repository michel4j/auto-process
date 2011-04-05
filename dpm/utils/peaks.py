'''
Created on Apr 5, 2011

@author: michel
'''


import numpy
from scipy.ndimage import measurements
from scipy.ndimage import filters

from bcm.utils.imageio import read_image


def detect_beam_peak(filename):
    img_info =read_image(filename)
    img = img_info.image
    img_array = numpy.fromstring(img.tostring(), numpy.uint32)
    img_array.shape = img.size[1], img.size[0]
      
    # filter the array so that features less than 8 pixels wide are blurred out
    # assumes that beam center is at least 8 pixels wide
    arr = filters.gaussian_filter(img_array, 8)
    beam_y, beam_x = measurements.maximum_position(arr)
    
    # valid beam centers must be within the center 1/5 region of the detector surface
    shape = img_array.shape
    cmin = [2 * v/5 for v in shape]
    cmax = [3 * v/5 for v in shape]
    good = False
    if cmin[0] < beam_y < cmax[0] and cmin[1] < beam_x < cmax[1]:
        good = True
        
    return beam_x, beam_y, good
    

