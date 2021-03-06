#!/usr/bin/env python
import rospy
from sensor_msgs.msg import LaserScan
from geometry_msgs.msg import Point
from sensor_msgs.msg import PointCloud
import numpy as np
from numpy import nan
from scipy import optimize

"""
https://scipy-cookbook.readthedocs.io/items/Least_Squares_Circle.html
"""


def pol2cart(rho, phi):
    x = rho * np.cos(phi)
    y = rho * np.sin(phi)
    return x, y

def pol2cart_arr(arr): #input: numpy array [rho, phi]
    x = arr[0] * np.cos(arr[1])
    y = arr[0] * np.sin(arr[1])
    return x, y

def cart2pol(x, y):
    rho = np.sqrt(x**2 + y**2)
    phi = np.arctan2(y, x)
    return(rho, phi)

def makebias(x,y): # makes inital bias before optimization.
    r, t = cart2pol(x,y)
    r = 1.0001*r
    return pol2cart(r,t)

def residuals(parameters,dataPoint):
    Ri = 85e-3/2
    xc,yc = parameters
    distance = [np.sqrt( (x-xc)**2 + (y-yc)**2 ) for x,y in dataPoint]
    res = [(Ri-dist)**2 for dist in distance]
    return res

def clustering(tup, angle_min, angle_inc):
    """ input: msg.ranges (type: tuple)
        output: List of numpy arrays. Each of the elements represents clustered point group.
                Its shape: (?,3), Each column along axis 1 represents index, range, and angle.
    """   
    data = tup
    num = 0
    temp_range = 0
    clustered_list = []
    for i, d in enumerate(data):
        dist = d - temp_range
        if np.isnan(d) and num == 0: pass
        
        elif (np.isnan(d) and num != 0) or (np.isnan(d)==False and num !=0 and abs(dist) >1):
            if num == 1: num = 0
            else:
                indices = [float(i) for i in range(i-num,i)]
                ranges = list(data[i-num+1:i+1])
                angles = [angle_min + e*angle_inc for e in indices]
                clustered_list.append(np.asarray([indices, ranges, angles]).transpose())
                num = 0
        else: num += 1
        temp_range = d
    return clustered_list

def callback(msg, pub_handle):
    pc = PointCloud()
    pc.header = msg.header
    
    clustered_data = clustering(msg.ranges, msg.angle_min, msg.angle_increment)
    
    reflector_coord = []
    
    for pts_pol in clustered_data: 
        pts_cart = np.apply_along_axis(pol2cart_arr, axis=1, arr=pts_pol[:,1:3])
        x_init, y_init = np.average(pts_cart[:,0]), np.average(pts_cart[:,1])
        x_bias, y_bias = makebias(x_init, y_init)
        estimated_val, ier = optimize.leastsq(residuals, [x_bias,y_bias],args=(pts_cart))
        reflector_coord.append(estimated_val)
    
    number_of_pixels = len(reflector_coord) # create an empty list of correct size
    pc.points = [None] * number_of_pixels
    for i, e in enumerate(reflector_coord):
        pc.points[i] = Point(e[0], e[1], 0)
    pub_handle.publish(pc)
    
if __name__ == '__main__':
    rospy.init_node("reflector_detector")
    pub = rospy.Publisher('pc_pub',PointCloud,queue_size=1)
    rospy.Subscriber("scan_filtered", LaserScan, callback, callback_args=(pub))
    rospy.spin()
