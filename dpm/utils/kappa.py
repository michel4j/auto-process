
from XO import XOconv, XOalign
from XO.ThreeAxisRotation2 import ThreeAxisRotation2
from XO.pycgtypes import vec3
from dpm.parser import xds
import math
import sys

r2d = 180/math.pi
radian2degree = lambda a: a*r2d
degree2radian = lambda a: a/r2d

ex, ey, ez = vec3(1,0,0), vec3(0,1,0), vec3(0,0,1)
X, Y, Z = ex, ey, ez
Qdnz2mos = XOconv.mat3T(ez, ex, ey)

class CustomParser(XOconv.XDSParser):
    def __init__(self, info):
        XOconv.XDSParser.__init__(self)
        self.parse_custom(info)
        self.debut()

    def parse_custom(self, info):
        "Extract information from info"
        self.dict["rot"] = info['rotation_axis']
        self.dict["beam"] = info['beam_axis']
        self.dict["distance"] = info['distance']
        self.dict["origin"] = info['det_origin']
        self.dict["originXDS"] = info['det_origin'] #!!!
        self.dict["A"] = info['cell_a_axis']
        self.dict["B"] = info['cell_b_axis']
        self.dict["C"] = info['cell_c_axis']
        self.dict["cell"] = info['unit_cell']
        self.dict["pixel_size"] = info['pixel_size']
        self.dict["pixel_numb"] = info['detector_size']
        self.dict["symmetry"] = info['sg_number']
        self.dict["detector_X"] = info['lab_x_axis']
        self.dict["detector_Y"] = info['lab_y_axis']
        self.dict["phi_init"] = info['start_angle']
        self.dict["num_init"] = info['first_frame']
        self.dict["delta_phi"] = info['delta_angle']
        self.dict["wavelength"] = info['wavelength']
        self.spaceGroupNumber = self.dict["symmetry"]
        self.spaceGroupName = XOconv.spg_num2symb[self.dict["symmetry"]]
        self.cell = self.dict["cell"]
        self.cell_r = XOconv.reciprocal(self.dict["cell"])

def main(GoniometerAxes, XOparser, mode, v1, v2, datum, pg_permute=True):

    # The goniostat consists of axes e1 carrying e2 carrying e3
    # (eg Omega, Kappa, Phi). GoniometerAxes = e1, e2, e3
    # gnsdtm calculate D from datum and GoniometerAxes.
    # D == Goniometer.tensor == datum matrix
    Goniometer = ThreeAxisRotation2((0.,0.,0.), GoniometerAxes, inversAxesOrder=0)

    # DATUM definition in degree.
    setDatum = tuple(datum) # in degree
    Goniometer.setAngles(map(degree2radian,setDatum))

    beam = XOconv.vec3(XOparser.dict['beam'])
    
    # MODE = 'CUSP' or 'MAIN'
    VL = XOalign.gnsmod(mode, beam, Goniometer)

    # V1/V2
    V1 = XOalign.CrystalVector(v1, printPrecision=4)
    V2 = XOalign.CrystalVector(v2, printPrecision=4)
    if "%s" % V1  != "%s" % V2:
        desiredSetting = V1, V2
    else:
        print "ERROR: The two crystal aligned vector can't be identical!"
        sys.exit(2)

    spgn = XOparser.dict['symmetry']

    pointGroup = XOconv.SPGlib[spgn][-1]
    Bmos = XOconv.BusingLevy(XOparser.cell_r)

    # Converting XDS XO to Mosflm convention
    UBmos = XOparser.UBxds_to_mos()/ XOparser.dict["wavelength"]
    Umos = (UBmos) * Bmos.inverse()
    XOconv.is_orthogonal(Umos)
    Bm1t = Bmos.inverse().transpose()
    orthogMatrices = {'rec':Bmos, 'dir':Bm1t}
    U0mos = Goniometer.tensor.inverse() * Umos # == gnsszr

    PG_permutions = [[X,Y,Z]]
    if pg_permute:
        PG_permutions.extend(XOconv.PGequiv[pointGroup])

    datumSolutions = XOalign.solve(desiredSetting, VL, orthogMatrices,
                              U0mos, Goniometer, PG_permutions)
    return datumSolutions

def get_solutions(info, orientations=("",""), mode='MAIN'):
    from XO.XOalign_sitedef import GONIOMETER_AXES, GONIOMETER_DATUM, GONIOMETER_AXES_NAMES, GONIOMETER_NAME
    
    _do_PG_permutations = True

    # Default orientation
    _v1, _v2 = map(str, orientations)
    XOparser = CustomParser(info)
    _space_group_numb =XOparser.dict['symmetry']

    if  _space_group_numb in [143, 144, 145, 149, 150, 151, 152, 153, 154, 168,
          169, 170, 171, 172, 173, 177, 178, 179, 180, 181, 182, 146, 155]:
        _do_PG_permutations = False # permutation option not available for Trigonal & Hexagonal

    all_solutions = {}
    if _v1 and _v2:
        allSets = ((_v1, _v2),)
    elif _v1 == "a*":
        allSets = (("a*", "b*"), ("a*", "c*"))
    elif _v1 == "b*":
        allSets = (("b*", "a*"), ("b*", "c*"))
    elif _v1 == "c*":
        allSets = (("c*", "a*"), ("c*", "b*"))
    else:
        allSets = (("a*", "b*"), ("a*", "c*"),
                   ("b*", "a*"), ("b*", "c*"),
                   ("c*", "a*"), ("c*", "b*"))
    
    for v1v2 in allSets:
        _v1, _v2 = v1v2
        all_solutions[v1v2] = main(GONIOMETER_AXES, XOparser, mode, _v1,
                              _v2, GONIOMETER_DATUM, pg_permute=_do_PG_permutations)
        #XOalign.print_solutions(all_solutions[v1v2], v1v2, GONIOMETER_AXES_NAMES)

    independent_solutions = {}
    for sols in all_solutions:
        for sol in all_solutions[sols]:
            key = "%6.1f %6.1f" % (sol[1],sol[0])
            if key not in independent_solutions:
                independent_solutions[key] = [(sol[1], sol[0]), sols]
            else:
                if sols not in independent_solutions[key]:
                    independent_solutions[key].append(sols)

    return independent_solutions.values(), {'mode': mode, 'goniometer': GONIOMETER_NAME}


if __name__ == '__main__':
    info = xds.parse_xparm('GXPARM.XDS')
    isols, pars = get_solutions(info)
    for n, isol in enumerate(isols):
        print "%4d %6.1f %6.1f  %s" % (n+1, isol[0][0], isol[0][1], isol[1:])
