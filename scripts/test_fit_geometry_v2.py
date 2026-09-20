"""Small analytic regression fixtures for the fit audit, not source-mesh proxies."""
import unittest
import numpy as np
from fit_geometry_v2 import surface_crossings,inside,point_triangle_distance

def cube(lo,hi):
 p=np.array([[x,y,z] for x in [lo,hi] for y in [lo,hi] for z in [lo,hi]],float)
 faces=[[0,1,3,2],[4,6,7,5],[0,4,5,1],[2,3,7,6],[0,2,6,4],[1,5,7,3]]
 return p[np.array([[f[0],f[k],f[k+1]] for f in faces for k in [1,2]])]
class FitChecks(unittest.TestCase):
 def test_disjoint_and_crossing(self):
  a=cube(0,1);self.assertFalse(surface_crossings(a,a+2)[0]);self.assertTrue(surface_crossings(a,a+.5)[0])
 def test_containment_without_surface_crossings(self):
  a=cube(0,1);b=cube(.2,.8);self.assertFalse(surface_crossings(a,b)[0]);self.assertTrue(inside(b.reshape(-1,3),a).all());self.assertFalse(inside(np.array([[2,2,2]]),a)[0])
 def test_coplanar_contact(self):
  a=np.array([[[0.,0,0],[1,0,0],[0,1,0]]]);self.assertTrue(surface_crossings(a,a)[0]);self.assertFalse(surface_crossings(a,a+[2,0,0])[0])
 def test_known_gap(self):
  tri=np.array([[[0.,0,0],[1,0,0],[0,1,0]]]);d=point_triangle_distance(np.array([[.2,.2,.001]]),tri);self.assertAlmostEqual(float(d[0]),.001,places=12)
if __name__=='__main__':unittest.main()
