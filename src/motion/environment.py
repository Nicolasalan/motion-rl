#!/usr/bin/env python3

# importar bibliotecas comuns
import os
import rospy
import numpy as np
import yaml
import math
import time
import tf

from geometry_msgs.msg import Twist
from sensor_msgs.msg import LaserScan
from nav_msgs.msg import Odometry
from gazebo_msgs.msg import ModelState

from std_srvs.srv import Empty
from squaternion import Quaternion

from utils import Extension

# folder to load config file
CONFIG_PATH = "/ws/src/motion/config/"

# Function to load yaml configuration file
def load_config(config_name):
    with open(os.path.join(CONFIG_PATH, config_name)) as file:
        param = yaml.safe_load(file)

    return param

param = load_config("main_config.yaml")

class Env():
     def __init__(self):

          # set the initial state
          self.goal_model = param["goal_model"]
          self.goal_reached_dist = param["goal_reached_dist"]
          self.environment_dim = param["environment_dim"]
          self.time_delta = param["time_delta"]
          self.collision_dist = param["collision_dist"]
          self.orientation_threshold = param["orientation_threshold"]
          self.util = Extension()

          # initialize global variables
          self.odom_x = 0.0
          self.odom_y = 0.0
          self.goal_x = 0.0
          self.goal_y = 0.0

          self.scan_data = np.ones(self.environment_dim) * 10
          self.path_waypoints = param["waypoints"]
          self.goals = self.util.path_goal(self.path_waypoints)
          self.pose = None
          self.orientation = None
          self.goal_orientation = 0.0

          # ROS publications and subscriptions
          self.pub_cmd_vel = rospy.Publisher(param["topic_cmd"], Twist, queue_size=10)
          self.odom = rospy.Subscriber(param["topic_odom"], Odometry, self.odom_callback, queue_size=10)
          self.scan = rospy.Subscriber(param["topic_scan"], LaserScan, self.scan_callback)

          # ROS services 
          self.reset = rospy.ServiceProxy('gazebo/reset_simulation', Empty)
          self.pause = rospy.ServiceProxy("/gazebo/pause_physics", Empty)
          self.unpause = rospy.ServiceProxy("/gazebo/unpause_physics", Empty)
          self.set_state = rospy.Publisher("gazebo/set_model_state", ModelState, queue_size=10)

          self.gaps = self.util.array_gaps(self.environment_dim)

     def odom_callback(self, odom_msg):
          """
          Processes an odometry message and updates the current pose of the robot.
          ======
          Params:
               odom_msg (Odometry): An odometry message containing the current pose of the robot.
               pose (Pose): The current pose of the robot, represented as a Pose object.
          """
          self.pose = odom_msg.pose.pose
          self.orientation = self.pose.orientation
     
     def scan_callback(self, scan):
          """
          Sensor scan message that contains range data from a laser range finder
          ======
          Params:
               scan (LaserScan): list of range measurements, one for each beam in the scan.
               scan_data (array): A list of range measurements.
          """
          data = scan.ranges
          self.scan_data = self.util.scan_rang(self.environment_dim, self.gaps, data)

     def step_env(self, action):
          """
          Traverse the environment in a robot simulation
          ======
          Params:
               action (array): linear and angular speeds based on action values
               state (array): array with robot states (leisure, speed, distance and theta)
               reward (gloat): agent reward function
               done (bool): check if it collided with an object
               target (bool): check if you reached the target
          """

          rospy.logwarn('Step Environment             => Stepping environment ...')
          target = False

          # ================== PUBLISH ACTION ================== #
          try:
               # Publish the robot action
               vel_cmd = Twist()
               vel_cmd.linear.x = action[0]
               vel_cmd.angular.z = action[1]
               self.pub_cmd_vel.publish(vel_cmd)
               rospy.loginfo('Publish Action               => Linear: ' + str(vel_cmd.linear.x) + ' Angular: ' + str(vel_cmd.angular.z))

          except:
               rospy.logerr('Publish Action              => Failed to publish action')

          # ================== UNPAUSE SIMULATION ================== #
          rospy.wait_for_service("/gazebo/unpause_physics")
          try:
               self.unpause()

               time.sleep(self.time_delta)

               rospy.wait_for_service("/gazebo/pause_physics")

               self.pause()
               
               rospy.loginfo('Unpause Simulation           => Unpause simulation ...')
          except:
               rospy.logerr('Unpause Simulation          => Error unpause simulation')

          # ================== READ SCAN DATA ================== #
          try:
               done, collision, min_laser = self.util.observe_collision(self.scan_data, self.collision_dist)
               v_state = []
               v_state[:] = self.scan_data[:]
               laser_state = [v_state]
               rospy.loginfo('Read Scan Data               => Min Lazer: ' + str(min_laser) + ' Collision: ' + str(collision) + ' Done: ' + str(done))
          
          except:
               rospy.logerr('Read Scan Data              => Error reading scan data')
               done = False
               collision = False
               min_laser = 0
               laser_state = [np.ones(self.environment_dim) * 10]

          # ================== READ ODOM DATA ================== #
          try:
               # Calculate robot heading from odometry data
               self.odom_x = self.pose.position.x
               self.odom_y = self.pose.position.y
               
               # Calculate robot heading from odometry data
               quaternion = Quaternion(
                    self.orientation.w,
                    self.orientation.x,
                    self.orientation.y,
                    self.orientation.z,
               )
               # calcule yaw angle

               euler = tf.transformations.euler_from_quaternion(quaternion)
               angle = round(euler[2], 4)
               print("Quaternion: ", quaternion, " Euler: ", euler)

               rospy.loginfo('Read Odom Data               => Odom X: ' + str(self.odom_x) + ' Odom Y: ' + str(self.odom_y) + ' Angle: ' + str(angle))

          except:
               rospy.logerr('Read Odom Data              => Error reading odometry data')
               self.odom_x = 1.0
               self.odom_y = 1.0
               angle = 0.0

          # ================== CALCULATE DISTANCE AND THETA ================== #
          # Calculate distance to the goal from the robot
          distance = self.util.distance_to_goal(self.odom_x, self.goal_x, self.odom_y, self.goal_y)
          # Calculate the relative angle between the robots heading and heading toward the goal
          theta = self.util.angles(self.odom_x, self.goal_x, self.odom_y, self.goal_y, angle)

          rospy.loginfo('Calculate distance and angle => Distance: ' + str(distance) + ' Angle: ' + str(theta))

          # ================== ORIENTATION GOAL ================== #
          # TODO:
          # Calculate difference between current orientation and target orientation
          #orientation_diff = abs(angle - self.goal_orientation)

          #rospy.loginfo('Orientation Goal             => Orientation Diff: ' + str(orientation_diff))

          # ================== CALCULATE DISTANCE AND ANGLE ================== #
          # Detect if the goal has been reached and give a large positive reward
          if distance < self.goal_reached_dist: #and orientation_diff < self.orientation_threshold:
               target = True
               done = True

          rospy.loginfo('Check (Collided or Arrive)   => Target: ' + str(target) + ' Done: ' + str(done))

          # ================== SET STATE ================== #
          robot_state = [distance, theta, action[0], action[1]]
          state = np.append(laser_state, robot_state)
          reward = self.util.get_reward(target, collision, action, min_laser)

          rospy.loginfo('Get Reward                   => Reward: ' + str(reward))
          return state, reward, done, target

     def reset_env(self):
          """
          Resets the environment to a new position and sets the initial robot states
          ======
          Params:
               state (array): array with robot states (leisure, speed, distance and theta)
          """

          # ================== RESET ENVIRONMENT ================== #
          rospy.logwarn("Reset Environment            => Resetting environment ...")
          # Resets the state of the environment and returns an initial observation.
          rospy.wait_for_service("/gazebo/reset_simulation")
          try:
               self.reset()

          except:
               rospy.logerr('Reset Simulation           => Failed service call failed')

          # ================== SET RANDOM ANGLE ================== #
          angle = np.random.uniform(-np.pi, np.pi)
          quaternion = Quaternion.from_euler(0.0, 0.0, angle)
          rospy.loginfo('Set Random Angle Robot       => Angle: ' + str(angle))

          # ================== SET RANDOM ORIENTATION ================== #
          try:
               self.goal_orientation = np.random.uniform(-np.pi, np.pi)

               rospy.loginfo('Set Random Angle Target      => Angle: ' + str(self.goal_orientation))
          
          except:
               rospy.logerr('Set Random Orientation      => Error setting random orientation')
               self.goal_orientation = 0.0

          # ================== SET RANDOM POSITION ================== #
          
          path = self.goals
          x, y = 0.0, 0.0

          while True:
               x, y = self.util.random_goal(path)
               _x, _y = self.util.change_goal(path, self.odom_x, self.odom_y)
               check = self.util.check_pose(x, y, _x, _y)
               if check == True:
                    break
                    
          rospy.loginfo('Set Random Position          => Goal: (' + str(x) + ', ' + str(y) + ') Robot: (' + str(self.odom_x) + ', ' + str(self.odom_y) + ')')

          # ================== SET RANDOM GOAL MODEL ================== #
          try:
               robot = ModelState()
               robot.model_name = "target"
               robot.pose.position.x = x
               robot.pose.position.y = y
               robot.pose.orientation.x = quaternion.x
               robot.pose.orientation.y = quaternion.y
               robot.pose.orientation.z = quaternion.z
               robot.pose.orientation.w = quaternion.w
               self.goal_x, self.goal_y = _x, _y
          
          except:
               rospy.logerr('Set Random Goal Model       => Error setting random goal model')

          # ================== UNPAUSE SIMULATION ================== #
          rospy.wait_for_service("/gazebo/unpause_physics")
          try:
               self.unpause()

               time.sleep(self.time_delta)

               rospy.wait_for_service("/gazebo/pause_physics")

               self.pause()
               
               rospy.loginfo('Unpause Simulation           => Unpause simulation ...')
          except:
               rospy.logerr('Unpause Simulation          => Error unpause simulation')

          # ================== GET STATE SCAN ================== #
          try:
               v_state = []
               v_state[:] = self.scan_data[:]
               laser_state = [v_state]

               rospy.loginfo('Get state scan               => Laser: ' + str(np.mean(laser_state)))
          except:
               rospy.logerr('Get state scan              => Error getting state scan')

          # ==================CALCULATE DISTANCE AND ANGLE ================== #
          # Calculate distance to the goal from the robot
          distance = self.util.distance_to_goal(self.odom_x, self.goal_x, self.odom_y, self.goal_y)
          # Calculate the relative angle between the robots heading and heading toward the goal
          theta = self.util.angles(self.odom_x, self.goal_x, self.odom_y, self.goal_y, angle)

          rospy.loginfo('Calculate distance and angle => Distance: ' + str(distance) + ' Angle: ' + str(theta))

          # ================== CREATE STATE ARRAY ================== #
          robot_state = [distance, theta, 0.0, 0.0]
          state = np.append(laser_state, robot_state)

          # ================== RETURN STATE ================== #
          return np.array(state)