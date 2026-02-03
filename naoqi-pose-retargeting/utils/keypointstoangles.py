"""
Taken and modified from
https://github.com/FraPorta/pepper_openpose_teleoperation
License: Apache 2.0
"""

import sys
import numpy as np
import math

## class KeypointsToAngles
#
# This class contains methods to receive 3D keypoints and calculate skeleton joint angles  
class KeypointsToAngles(object):
    '''
# Mediapipe Mapping:
  NOSE = 0
  LEFT_EYE_INNER = 1
  LEFT_EYE = 2
  LEFT_EYE_OUTER = 3
  RIGHT_EYE_INNER = 4
  RIGHT_EYE = 5
  RIGHT_EYE_OUTER = 6
  LEFT_EAR = 7
  RIGHT_EAR = 8
  MOUTH_LEFT = 9
  MOUTH_RIGHT = 10
  LEFT_SHOULDER = 11
  RIGHT_SHOULDER = 12
  LEFT_ELBOW = 13
  RIGHT_ELBOW = 14
  LEFT_WRIST = 15
  RIGHT_WRIST = 16
  LEFT_PINKY = 17
  RIGHT_PINKY = 18
  LEFT_INDEX = 19
  RIGHT_INDEX = 20
  LEFT_THUMB = 21
  RIGHT_THUMB = 22
  LEFT_HIP = 23
  RIGHT_HIP = 24
  LEFT_KNEE = 25
  RIGHT_KNEE = 26
  LEFT_ANKLE = 27
  RIGHT_ANKLE = 28
  LEFT_HEEL = 29
  RIGHT_HEEL = 30
  LEFT_FOOT_INDEX = 31
  RIGHT_FOOT_INDEX = 32


    # OpenPose Mapping
    body_mapping = {'0':  "Nose", 
                    '1':  "Neck", 
                    '2':  "RShoulder",
                    '3':  "RElbow",
                    '4':  "RWrist",
                    '5':  "LShoulder",
                    '6':  "LElbow",
                    '7':  "LWrist",
                    '8':  "MidHip"}
    '''

    ##  method __init__
    #
    #   Initialization method 
    def __init__(self):
        # init start flag
        self.start_flag = True

        # initialize socket for receiving the 3D keypoints

    ##  method stop_receiving
    #
    #   stop the receive keypoints loop
    def stop_receiving(self):
        self.start_flag = False

    ##  function vector_from_points
    #
    #   calculate 3D vector from two points ( vector = P2 - P1 )
    def vector_from_points(self, P1, P2):
        vector = [P2[0] - P1[0], P2[1] - P1[1], P2[2] - P1[2]]
        return vector

    ##  function obtain_LShoulderPitchRoll_angles
    # 
    #   Calculate left shoulder pitch and roll angles
    def obtain_LShoulderPitchRoll_angles(self, P1, P5, P6, P8):
        # Construct 3D vectors (bones) from points
        v_1_5 = self.vector_from_points(P1, P5)
        v_5_1 = self.vector_from_points(P5, P1)
        v_6_5 = self.vector_from_points(P6, P5)
        v_5_6 = self.vector_from_points(P5, P6)

        # # Calculate normal of the 1_5_6 plane
        # n_1_5_6 = np.cross(v_1_5, v_6_5)

        # Left torso Z axis
        v_8_1 = self.vector_from_points(P8, P1)

        # Left torso X axis 
        n_8_1_5 = np.cross(v_8_1, v_5_1)
        # n_8_1_5 = np.cross(v_5_1, v_8_1)

        # Left torso Y axis
        # R_left_torso = np.cross(v_8_1, n_8_1_5)
        R_left_torso = np.cross(n_8_1_5, v_8_1) # Left-right arm inverted

        x = np.dot(v_5_6, v_8_1) / (np.linalg.norm(v_5_6))*(np.linalg.norm(v_8_1))
        # Intermediate angle to calculate positive or negative final Pitch angle
        try:
            intermediate_angle = math.acos(x)
        except ValueError:
            intermediate_angle = np.pi/2
        # intermediate_angle = np.arccos(x, where=(abs(x)<1), out=np.full_like(x, np.pi/2))
        
        # Module of the LShoulderPitch angle
        x = np.dot(v_8_1, np.cross(R_left_torso, v_5_6))/(np.linalg.norm(v_8_1) * np.linalg.norm(np.cross(R_left_torso, v_5_6))) 
        try:
            theta_LSP_module = math.acos(x)
        except ValueError:
            theta_LSP_module = 0
        # theta_LSP_module = np.arccos(x, where=(abs(x)<1), out=np.full_like(x, 0))

        # Positive or negative LShoulderPitch
        if intermediate_angle <= np.pi/2 :
            LShoulderPitch = -theta_LSP_module
        else:
            LShoulderPitch = theta_LSP_module
    
        # Formula for LShoulderRoll
        # LShoulderRoll = (np.pi/2) - np.arccos((np.dot(v_5_6, R_left_torso)) / (np.linalg.norm(v_5_6) * np.linalg.norm(R_left_torso)))
        x = (np.dot(v_5_6, R_left_torso)) / (np.linalg.norm(v_5_6) * np.linalg.norm(R_left_torso))
        try:
            LShoulderRoll = math.acos(x) - (np.pi/2)
        except ValueError:
            LShoulderRoll = 0
        # LShoulderRoll =  np.arccos(x, where=(abs(x)<1), out=np.full_like(x, 0)) - (np.pi/2) # Left-right arm inverted
        
        # Return LShoulder angles
        return LShoulderPitch, LShoulderRoll
    
    ##  function obtain_RShoulderPitchRoll_angles
    # 
    #   Calculate right shoulder pitch and roll angles
    def obtain_RShoulderPitchRoll_angles(self, P1, P2, P3, P8):
        # Construct 3D vectors (bones) from points
        v_2_3 = self.vector_from_points(P2, P3)
        v_1_2 = self.vector_from_points(P1, P2)
        v_2_1 = self.vector_from_points(P2, P1)

        # Right torso Z axis
        v_8_1 = self.vector_from_points(P8, P1)
        # Right torso X axis
        n_8_1_2 = np.cross(v_8_1, v_1_2)
        # Right torso Y axis
        # R_right_torso = np.cross(v_8_1, n_8_1_2) 
        R_right_torso = np.cross(n_8_1_2,v_8_1) # Left-right arm inverted

        # # Normal to plane 1_2_3
        # n_1_2_3 = np.cross(v_2_3, v_2_1)

        # Module of the RShoulderPitch angle
        x = np.dot(v_8_1, np.cross(R_right_torso, v_2_3))/(np.linalg.norm(v_8_1) * np.linalg.norm(np.cross(R_right_torso, v_2_3)))
        try:
            theta_RSP_module = math.acos(x)
        except ValueError:
            theta_RSP_module = 0
        # theta_RSP_module = np.arccos(x, where=(abs(x)<1), out=np.full_like(x, 0))
        
        # Intermediate angle to calculate positive or negative final Pitch angle
        x = np.dot(v_2_3, v_8_1) / (np.linalg.norm(v_2_3))*(np.linalg.norm(v_8_1))
        try:
            intermediate_angle = math.acos(x)
        except ValueError:
            intermediate_angle = np.pi/2
        # intermediate_angle = np.arccos(x, where=(abs(x)<1), out=np.full_like(x, np.pi/2))

        # Positive or negative RShoulderPitch
        if intermediate_angle <= np.pi/2 :
            RShoulderPitch = - theta_RSP_module
        else:
            RShoulderPitch = theta_RSP_module

        # Formula for RShoulderRoll
        # RShoulderRoll =  (np.pi/2) - np.arccos((np.dot(v_2_3, R_right_torso)) / (np.linalg.norm(v_2_3) * np.linalg.norm(R_right_torso))) 
        x = (np.dot(v_2_3, R_right_torso)) / (np.linalg.norm(v_2_3) * np.linalg.norm(R_right_torso))
        try:
            RShoulderRoll = math.acos(x) - (np.pi/2)
        except ValueError:
            RShoulderRoll = np.pi/2
        # RShoulderRoll =  np.arccos(x, where=(abs(x)<1), out=np.full_like(x, 0)) - (np.pi/2) # Left-right arm inverted

        # Return RShoulder angles
        return RShoulderPitch, RShoulderRoll

    ##  function obtain_LElbowYawRoll_angle
    #   
    #   Calculate left elbow yaw and roll angles
    def obtain_LElbowYawRoll_angle(self, P1, P5, P6, P7):
        # Construct 3D vectors (bones) from points
        v_6_7 = self.vector_from_points(P6, P7)
        v_1_5 = self.vector_from_points(P1, P5)

        # Left arm Z axis
        v_6_5 = self.vector_from_points(P6, P5)
        # Left arm X axis
        # n_1_5_6 = np.cross(v_6_5, v_1_5) 
        n_1_5_6 = np.cross(v_1_5, v_6_5) # Right-Left arms inverted
        # Left arm Y axis
        R_left_arm = np.cross(v_6_5, n_1_5_6)

        # Normal of 5_6_7 plane
        n_5_6_7 = np.cross(v_6_5, v_6_7) 

        # Formula to calculate the module of LElbowYaw angle
        x = np.dot(n_1_5_6, n_5_6_7) / (np.linalg.norm(n_1_5_6) * np.linalg.norm(n_5_6_7))
        try:
            theta_LEY_module = math.acos(x)
        except ValueError:
            theta_LEY_module = 0
        # theta_LEY_module = np.arccos(x, where=(abs(x)<1), out=np.full_like(x, 0)) 

        # Intermediate angles to choose the right LElbowYaw angle
        x = np.dot(v_6_7, n_1_5_6) / (np.linalg.norm(v_6_7) * np.linalg.norm(n_1_5_6))
        try:
            intermediate_angle_1 = math.acos(x)
        except ValueError:
            intermediate_angle_1 = np.pi/2
        # intermediate_angle_1 = np.arccos(x, where=(abs(x)<1), out=np.full_like(x, np.pi/2))

        x = np.dot(v_6_7, R_left_arm) / (np.linalg.norm(v_6_7) * np.linalg.norm(R_left_arm))
        try:
            intermediate_angle_2 = math.acos(x)
        except ValueError:
            intermediate_angle_2 = np.pi/2
        # intermediate_angle_2 = np.arccos(x, where=(abs(x)<1), out=np.full_like(x, np.pi/2))

        # Choice of the correct LElbowYaw angle using intermediate angles values
        if intermediate_angle_1 <= np.pi/2:
            LElbowYaw = -theta_LEY_module 
        else:
            if intermediate_angle_2 > np.pi/2:
                LElbowYaw = theta_LEY_module 
            elif intermediate_angle_2 <= np.pi/2:
                LElbowYaw = theta_LEY_module - (2 * np.pi)

        # Formula for LElbowRoll angle
        x = np.dot(v_6_7, v_6_5) / (np.linalg.norm(v_6_7) * np.linalg.norm(v_6_5))
        try:
            LElbowRoll = math.acos(x) - np.pi
        except ValueError:
            LElbowRoll = 0
        # LElbowRoll = np.arccos(x, where=(abs(x)<1), out=np.full_like(x, 0)) - np.pi
        # print('Before', LElbowYaw*180/np.pi, LElbowRoll*180/np.pi)
        # Return LElbow angles
        return LElbowYaw, LElbowRoll

 
    ##  function obtain_RElbowYawRoll_angle
    # 
    #   Calculate right elbow yaw and roll angles
    def obtain_RElbowYawRoll_angle(self, P1, P2, P3, P4):
        # Construct 3D vectors (bones) from points
        v_3_4 = self.vector_from_points(P3, P4)
        v_1_2 = self.vector_from_points(P1, P2)

        # Left arm Z axis
        v_3_2 = self.vector_from_points(P3, P2)
        # Left arm X axis
        # n_1_2_3 = np.cross(v_3_2, v_1_2)  # -- OUT --
        n_1_2_3 = np.cross(v_1_2, v_3_2)    # -- IN --  Right-left arms inverted
        # Left arm Y axis
        R_right_arm = np.cross(v_3_2, n_1_2_3)

        # normal to the 2_3_4 plane
        n_2_3_4 = np.cross(v_3_2, v_3_4)
        # n_2_3_4 = np.cross(v_3_4, v_3_2)


        # Formula to calculate the module of RElbowYaw angle
        x = np.dot(n_1_2_3, n_2_3_4) / (np.linalg.norm(n_1_2_3) * np.linalg.norm(n_2_3_4))
        try:
            theta_REY_module = math.acos(x)
        except ValueError:
            theta_REY_module = 0
        # theta_REY_module = np.arccos(x, where=(abs(x)<1), out=np.full_like(x, 0))

        # Intermediate angles to choose the right RElbowYaw angle
        x = np.dot(v_3_4, n_1_2_3) / (np.linalg.norm(v_3_4) * np.linalg.norm(n_1_2_3))
        try:
            intermediate_angle_1 = math.acos(x)
        except ValueError:
            intermediate_angle_1 =  np.pi/2
        # intermediate_angle_1 = np.arccos(x, where=(abs(x)<1), out=np.full_like(x, np.pi/2))

        x = np.dot(v_3_4, R_right_arm) / (np.linalg.norm(v_3_4) * np.linalg.norm(R_right_arm))
        try:
            intermediate_angle_2 = math.acos(x)
        except ValueError:
            intermediate_angle_2 =  np.pi/2
        # intermediate_angle_2 = np.arccos(x, where=(abs(x)<1), out=np.full_like(x, np.pi/2))

        # Choice of the correct RElbowYaw angle using intermediate angles values
        if intermediate_angle_1 <= np.pi/2:
            RElbowYaw = -theta_REY_module
        else:
            if intermediate_angle_2 > np.pi/2:
                RElbowYaw = theta_REY_module
            elif intermediate_angle_2 <= np.pi/2:
                # RElbowYaw = -theta_REY_module + (2 * np.pi)
                RElbowYaw = theta_REY_module 
        
        # Formula for RElbowRoll angle
        x = np.dot(v_3_4, v_3_2) / (np.linalg.norm(v_3_4) * np.linalg.norm(v_3_2))
        try:
            RElbowRoll =  np.pi - math.acos(x)
        except ValueError:
            RElbowRoll =  0
        # RElbowRoll = np.pi - np.arccos(x, where=(abs(x)<1), out=np.full_like(x, 0))

        # print('Before', RElbowYaw*180/np.pi, RElbowRoll*180/np.pi)
        # Return RElbow angles
        return RElbowYaw, RElbowRoll
    
    ##  function obtain_HipPitch_angles
    # 
    #   Calculate right hip pitch angle
    def obtain_HipPitch_angles(self, P0_curr, P8_curr):
        """
        Hip pitch using mid-hip -> neck vector on YZ plane.
        MediaPipe world coords: y 朝下（相机坐标），z 朝前为负。
        直立: HipPitch ~ 0；前屈: HipPitch 更小（负），后仰: 更大（正）。
        """
        v = np.array(self.vector_from_points(P0_curr, P8_curr), dtype=float)

        # 重新定义朝上的分量（因为 mediapipe y 朝下）
        y_up = -v[1]
        z_forward = -v[2]  # 朝前为正

        if np.isclose(y_up, 0) and np.isclose(z_forward, 0):
            return 0.0

        # atan2 范围 (-pi, pi)，这里取反以满足“前屈更小”的约定
        HipPitch = -math.atan2(z_forward, y_up if not np.isclose(y_up, 0) else 1e-8)
        return HipPitch

    ##  function obtain_HeadPitch_angle
    #
    #   Calculate head pitch (nodding) angle using neck and nose points
    def obtain_HeadPitch_angle(self, neck_point, nose_point):
        # 转为向量并只关注 Y（下为正）和 Z（向屏幕内为负）分量
        v = np.array(self.vector_from_points(neck_point, nose_point), dtype=float)
        vy = v[1]
        vz_forward = -v[2]  # z 向前为正

        if np.isclose(vy, 0) and np.isclose(vz_forward, 0):
            return 0.0

        # 以前倾为正：vy 增大（点头）、vz_forward 为正，抬头时 vy 为负
        HeadPitch = math.atan2(vy, vz_forward if not np.isclose(vz_forward, 0) else 1e-8)
        return HeadPitch
    
