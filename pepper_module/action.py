
class PepperAction:
    def __init__(self, motion):
        self.motion = motion

    def bow(self):
        joint_names = ["HeadPitch", "HipPitch", "LShoulderPitch", "LShoulderRoll", 
                      "LElbowYaw", "LElbowRoll", "LWristYaw"]
        
        times = [
            [0.0, 1.5, 3.0],  # HeadPitch
            [0.0, 1.5, 3.0],  # HipPitch
            [0.0, 1.5, 3.0],  # LShoulderPitch
            [0.0, 1.5, 3.0],  # LShoulderRoll
            [0.0, 1.5, 3.0],  # LElbowYaw
            [0.0, 1.5, 3.0],  # LElbowRoll
            [0.0, 1.5, 3.0]   # LWristYaw
        ]

        control_points = [
            [0.0, 60.0, 0.0],      # HeadPitch
            [0.0, -30.0, 0.0],     # HipPitch
            [101.3, 55.8, 101.3],  # LShoulderPitch
            [5.5, 5.6, 5.5],       # LShoulderRoll
            [-98.3, -14.5, -98.3], # LElbowYaw
            [-5.9, -57.1, -5.9],   # LElbowRoll
            [10.1, -52.7, 10.1]    # LWristYaw
        ]
        angles_radians = []
        for row in control_points:
            row_radians = []
            for angle in row:
                row_radians.append(angle * 3.1415 / 180)
            angles_radians.append(row_radians)
        self.motion.angleInterpolationBezier(joint_names, times, angles_radians)
    def shy(self):
            joint_names = ["HeadPitch", "HipPitch", "LShoulderPitch", "LShoulderRoll", "LElbowYaw", "LElbowRoll", "LWristYaw","RShoulderPitch", "RShoulderRoll", "RElbowYaw", "RElbowRoll", "RWristYaw", "LHand", "RHand"]
            times = [
                [0.0, 1.0, 3.0,4.0],  # HeadPitch
                [0.0, 1.0, 3.0,4.0],  # HipPitch
                [0.0, 1.0, 3.0,4.0],  # LShoulderPitch
                [0.0, 1.0, 3.0,4.0],  # LShoulderRoll
                [0.0, 1.0, 3.0,4.0],  # LElbowYaw
                [0.0, 1.0, 3.0,4.0],  # LElbowRoll
                [0.0, 1.0, 3.0,4.0],   # LWristYaw
                [0.0, 1.0, 3.0,4.0],  # RShoulderPitch
                [0.0, 1.0, 3.0,4.0],  # RShoulderRoll
                [0.0, 1.0, 3.0,4.0],  # RElbowYaw
                [0.0, 1.0, 3.0,4.0],  # RElbowRoll
                [0.0, 1.0, 3.0,4.0],   # RWristYaw
                [0.0, 1.0, 3.0,4.0],  # LHand
                [0.0, 1.0, 3.0,4.0]   # RHand
            ]
            control_points = [
                [0.0, 30.0,30.0, 0.0],  # HeadPitch:
                [0.0, 0, 0,0.0],   # HipPitch:
                [101.3, 24.6,24.6, 101.3],  # LShoulderPitch:
                [5.5, 6.5,6.5, 5.5],  # LShoulderRoll:
                [-98.3, -64.7,-64.7, -98.3],  # LElbowYaw:
                [-5.9, -89.4,-89.4, -5.9],  # LElbowRoll:
                [10.1, -74.8,-74.8, 10.1],   # LWristYaw:
                [101.3, 24.6,24.6, 101.3],  # RShoulderPitch:
                [-5.5, -6.5,-6.5, -5.5],  # RShoulderRoll:
                [98.3, 64.7,64.7, 98.3],  # RElbowYaw:
                [5.9, 89.4,89.4, 5.9],  # RElbowRoll:
                [-10.1, 74.8,74.8, -10.1],   # RWristYaw:
            ]

            angles_radians = []
            for row in control_points:
                row_radians = []
                for angle in row:
                    row_radians.append(angle * 3.1415 / 180)
                angles_radians.append(row_radians)
            angles_radians.append([0.6, 1.0,1.0, 0.6])#LHand
            angles_radians.append([0.6, 1.0,1.0, 0.6])#RHand
            self.motion.angleInterpolationBezier(joint_names, times, angles_radians)
    def proud(self):
            joint_names = ["HeadPitch", "HipPitch", "LShoulderPitch", "LShoulderRoll", "LElbowYaw", "LElbowRoll", "LWristYaw","RShoulderPitch", "RShoulderRoll", "RElbowYaw", "RElbowRoll", "RWristYaw", "LHand", "RHand"]
            times = [
                [0.0, 1.0, 3.0,4.0],  # HeadPitch
                [0.0, 1.0, 3.0,4.0],  # HipPitch
                [0.0, 1.0, 3.0,4.0],  # LShoulderPitch
                [0.0, 1.0, 3.0,4.0],  # LShoulderRoll
                [0.0, 1.0, 3.0,4.0],  # LElbowYaw
                [0.0, 1.0, 3.0,4.0],  # LElbowRoll
                [0.0, 1.0, 3.0,4.0],   # LWristYaw
                [0.0, 1.0, 3.0,4.0],  # RShoulderPitch
                [0.0, 1.0, 3.0,4.0],  # RShoulderRoll
                [0.0, 1.0, 3.0,4.0],  # RElbowYaw
                [0.0, 1.0, 3.0,4.0],  # RElbowRoll
                [0.0, 1.0, 3.0,4.0],   # RWristYaw
                [0.0, 1.0, 3.0,4.0],  # LHand
                [0.0, 1.0, 3.0,4.0]   # RHand
            ]
            control_points = [
                [0.0, -23.7,-23.7, 0.0],  # HeadPitch:
                [0.0, 0, 0,0.0],   # HipPitch:
                [101.3, 98.7,98.7, 101.3],  # LShoulderPitch:
                [5.5, 42.2,42.3, 5.5],  # LShoulderRoll:
                [-98.3, -29.2,-29.2, -98.3],  # LElbowYaw:
                [-5.9, -71.1,-71.1, -5.9],  # LElbowRoll:
                [10.1, -27.2,-27.2, 10.1],   # LWristYaw:
                [101.3, 98.7,98.7, 101.3],  # RShoulderPitch:
                [-5.5, -42.2,-42.3, -5.5],  # RShoulderRoll:
                [98.3, 29.2,29.2, 98.3],  # RElbowYaw:
                [5.9, 71.1,71.1, 5.9],  # RElbowRoll:
                [-10.1, 27.2,27.2, -10.1],   # RWristYaw:
            ]

            angles_radians = []
            for row in control_points:
                row_radians = []
                for angle in row:
                    row_radians.append(angle * 3.1415 / 180)
                angles_radians.append(row_radians)
            angles_radians.append([0.6, 1.0,1.0, 0.6])#LHand
            angles_radians.append([0.6, 1.0,1.0, 0.6])#RHand
            self.motion.angleInterpolationBezier(joint_names, times, angles_radians)
    def think(self):
            joint_names = ["HeadPitch", "KneePitch","HipPitch", "LShoulderPitch", "LShoulderRoll", "LElbowYaw", "LElbowRoll", "LWristYaw","RShoulderPitch", "RShoulderRoll", "RElbowYaw", "RElbowRoll", "RWristYaw", "LHand", "RHand"]
            times = [
                [0.0, 1.0, 3.0,4.0],  # HeadPitch
                [0.0, 1.0, 3.0,4.0],  # KneePitch
                [0.0, 1.0, 3.0,4.0],  # HipPitch
                [0.0, 1.0, 3.0,4.0],  # LShoulderPitch
                [0.0, 1.0, 3.0,4.0],  # LShoulderRoll
                [0.0, 1.0, 3.0,4.0],  # LElbowYaw
                [0.0, 1.0, 3.0,4.0],  # LElbowRoll
                [0.0, 1.0, 3.0,4.0],   # LWristYaw
                [0.0, 1.0, 3.0,4.0],  # RShoulderPitch
                [0.0, 1.0, 3.0,4.0],  # RShoulderRoll
                [0.0, 1.0, 3.0,4.0],  # RElbowYaw
                [0.0, 1.0, 3.0,4.0],  # RElbowRoll
                [0.0, 1.0, 3.0,4.0],   # RWristYaw
                [0.0, 1.0, 3.0,4.0],  # LHand
                [0.0, 1.0, 3.0,4.0]   # RHand
            ]
            control_points = [
                [0.0,6.5,6.5,0.0],  # HeadPitch:
                [0.0,20.6,20.6,0.0],  # KneePitch:
                [0.0,-46.1,-46.1,0.0],   # HipPitch:
                [101.3, 24.4,24.4, 101.3],  # LShoulderPitch:
                [5.5, 6.9,6.9, 5.5],  # LShoulderRoll:
                [-98.3, -55.3,-55.3, -98.3],  # LElbowYaw:
                [-5.9, -89.3,-89.3, -5.9],  # LElbowRoll:
                [10.1, -73.8,-73.8, 10.1],   # LWristYaw:
                [101.3, 71.4,71.4, 101.3],  # RShoulderPitch:
                [-5.5, -5.5,-5.5, -5.5],  # RShoulderRoll:
                [98.3, 98.3,98.3, 98.3],  # RElbowYaw:
                [5.9, 5.9,5.9, 5.9],  # RElbowRoll:
                [-10.1, -10.1,-10.1, -10.1],   # RWristYaw:
            ]

            angles_radians = []
            for row in control_points:
                row_radians = []
                for angle in row:
                    row_radians.append(angle * 3.1415 / 180)
                angles_radians.append(row_radians)
            angles_radians.append([0.6, 1.0,1.0, 0.6])#LHand
            angles_radians.append([0.6, 0.6,0.6, 0.6])#RHand
            self.motion.angleInterpolationBezier(joint_names, times, angles_radians)
    def salute(self):
            joint_names = ["HeadPitch", "HipPitch", "LShoulderPitch", "LShoulderRoll", "LElbowYaw", "LElbowRoll", "LWristYaw","RShoulderPitch", "RShoulderRoll", "RElbowYaw", "RElbowRoll", "RWristYaw", "LHand", "RHand"]
            times = [
                [0.0, 1.0, 3.0,4.0],  # HeadPitch
                [0.0, 1.0, 3.0,4.0],  # HipPitch
                [0.0, 1.0, 3.0,4.0],  # LShoulderPitch
                [0.0, 1.0, 3.0,4.0],  # LShoulderRoll
                [0.0, 1.0, 3.0,4.0],  # LElbowYaw
                [0.0, 1.0, 3.0,4.0],  # LElbowRoll
                [0.0, 1.0, 3.0,4.0],   # LWristYaw
                [0.0, 1.0, 3.0,4.0],  # RShoulderPitch
                [0.0, 1.0, 3.0,4.0],  # RShoulderRoll
                [0.0, 1.0, 3.0,4.0],  # RElbowYaw
                [0.0, 1.0, 3.0,4.0],  # RElbowRoll
                [0.0, 1.0, 3.0,4.0],   # RWristYaw
                [0.0, 1.0, 3.0,4.0],  # LHand
                [0.0, 1.0, 3.0,4.0]   # RHand
            ]
            control_points = [
                [0.0, -23.7,-23.7, 0.0],  # HeadPitch:
                [0.0, 0, 0,0.0],   # HipPitch:
                [101.3, 101.3,101.3, 101.3],  # LShoulderPitch:
                [5.5, 5.5,5.5, 5.5],  # LShoulderRoll:
                [-98.3, -98.3,-98.3, -98.3],  # LElbowYaw:
                [-5.9, -5.9,-5.9, -5.9],  # LElbowRoll:
                [10.1, 10.1,10.1, 10.1],   # LWristYaw:
                [101.3, -71.1,-71.1, 101.3],  # RShoulderPitch:
                [-5.5, -37.3,-37.3, -5.5],  # RShoulderRoll:
                [98.3, 17.9,17.9, 98.3],  # RElbowYaw:
                [5.9, 77.9,77.9, 5.9],  # RElbowRoll:
                [-10.1, 88.3,88.3, -10.1],   # RWristYaw:
            ]

            angles_radians = []
            for row in control_points:
                row_radians = []
                for angle in row:
                    row_radians.append(angle * 3.1415 / 180)
                angles_radians.append(row_radians)
            angles_radians.append([0.6, 1.0,1.0, 0.6])#LHand
            angles_radians.append([0.6, 0.6,0.6, 0.6])#RHand
            self.motion.angleInterpolationBezier(joint_names, times, angles_radians)
    def customize(self, joint_names, times, control_points):
        #angles_radians = []
        #for row in control_points:
        #    row_radians = []
        #    for angle in row:
        #        row_radians.append(angle * 3.1415 / 180)
        #    angles_radians.append(row_radians)
        self.motion.angleInterpolationBezier(joint_names, times, control_points)