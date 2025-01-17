from threading import Thread,Event ,Lock 
from queue import Queue
import time
import cflib.crtp
from cflib.crazyflie.swarm import CachedCfFactory
from cflib.crazyflie.swarm import Swarm
import math
from cflib.crazyflie import syncCrazyflie
from cflib.crazyflie.log import LogConfig
from cflib.positioning.motion_commander import MotionCommander
import rclpy
from std_msgs.msg import Int32
from std_msgs.msg import Float64MultiArray
from rclpy.node import Node
from std_msgs.msg import Int32MultiArray
from std_msgs.msg import Bool
from geometry_msgs.msg import TransformStamped, Vector3
from tf2_ros import TransformBroadcaster

from nav_msgs.msg import Path

#drone radios channels

A = 'radio://0/100/2M/E7E7E7E700' # N
B = 'radio://0/100/2M/E7E7E7E701'
C = 'radio://0/100/2M/E7E7E7E707'  # F 
D = 'radio://0/100/2M/E7E7E7E706' # Y

uris = [B,C]

class MinimalPublisher(Node):
    
    global uris
    #global Drone
    global event
    event = Event()
    global lock
    


    def __init__(self):
        super().__init__('minimal_publisher')
        cflib.crtp.init_drivers()
        self.factory = CachedCfFactory(rw_cache='./cache')
        self.publishernode()
        self.SubcriberNode()
        print("spinning")
        # rclpy.spin(self)
        self.start()

    def publishernode(self):
        self.publisher_ = self.create_publisher(Int32, 'num_drones', 10)
        self.publisher_1 = self.create_publisher(Float64MultiArray,'drones_states',10)
        self.publisher_active =self.create_publisher(Int32MultiArray,'drones_active',10)
        self.publisher_waypoints=self.create_publisher(Float64MultiArray,'drones_goals',10)
        self.publisher_radii = self.create_publisher(Float64MultiArray,'drones_radii',10)
        self.tf_broadcaster = TransformBroadcaster(self)
        timer_period = 0.05 # seconds
        print("start")
        self.position_data = dict()
        self.waypoint_data =dict()
        self.path_dict =dict()
        self.path_found =dict()
        self.float_list = Float64MultiArray()
        self.drone_active_list=Int32MultiArray()
        self.waypoint_publisher = Float64MultiArray()
        self.radius_list = Float64MultiArray()
        self.number_drones=len(uris)
        self.float_list.data = [0.0]*4*self.number_drones
        self.drone_active_list.data =[1]*self.number_drones
        self.radius_list.data =[0.15]*self.number_drones
        self.waypoint_publisher.data = [0.0]*2*self.number_drones
    
    def timer_callback(self):
        # print("in timer")
        msg = Int32()
        self.number_drones=len(uris)
        msg.data = self.number_drones
        self.publisher_.publish(msg)
        #print("creating drones instance")

        self.publisher_active.publish(self.drone_active_list)

        self.publisher_radii.publish(self.radius_list)
        
        for i in range(self.number_drones):
            try:
                self.float_list.data[i*4] = self.position_data.get(uris[i])[0]
                self.float_list.data[i*4+1] =self.position_data.get(uris[i])[1]
                self.float_list.data[i*4+2] = self.position_data.get(uris[i])[2]
                self.float_list.data[i*4+3] = self.position_data.get(uris[i])[3]
            except:
                print("skipping once")
        #print(self.float_list)
        self.publisher_1.publish(self.float_list)

        for i in range(self.number_drones):
            try:
                self.waypoint_publisher.data[i*2] =   self.waypoint_data.get(uris[i])[0]
                self.waypoint_publisher.data[i*2+1] = self.waypoint_data.get(uris[i])[1]
            except:
                print("skipping waypoint once")
        #print(self.waypoint_publisher)
        self.publisher_waypoints.publish(self.waypoint_publisher)
        self.Transform_Publisher()

    def Transform_Publisher(self):
        for i in range(self.number_drones):
            tf_msg = TransformStamped()
            tf_msg.header.frame_id = 'odom'
            tf_msg.child_frame_id = str("drone")+str(i)
            tf_msg.header.stamp = self.get_clock().now().to_msg()

            try:
                tf_msg.transform.translation.x = self.position_data.get(uris[i])[0]
                tf_msg.transform.translation.y = self.position_data.get(uris[i])[1]
                #tf_msg.transform.translation.y = self.position_data.get(uris[i])[1]
        

                self.tf_broadcaster.sendTransform(tf_msg)
            except:
                print("skipping first trnsform publishin")


    """
    subcriber node 
    """

    def SubcriberNode(self):
        self.topics_create()
        print(self.path_topics)
        print(self.path_found_topic)
        self.current_path = []
        self.subcriber_list = []
        self.subcriber_path_found_list =[]
        self.path_found_list=[]
        for i in range(self.number_drones):

            self.current_path.append([1, 1])
            self.path_found_list.append(0)
            
        for i in range(0, self.number_drones):
            print("creating subscription")
            subscriber_path = self.create_subscription(
                Path,
                self.path_topics[i],
                self.path_callback_generator(i),
                10
            )
            self.subcriber_list.append(subscriber_path) 
            subscriber_path_found = self.create_subscription(
                Bool,
                self.path_found_topic[i],
                self.update_path_found_generator(i),
                10
            ) 
            self.subcriber_path_found_list.append(subscriber_path_found)

    def topics_create(self):
        self.path_topics=[]
        self.path_found_topic = []   
        for i in range(self.number_drones):
            topic=str('/drone_path')+str(i)
            found=str('/drone_path')+str(i)+str('found')
            self.path_topics.append(topic)
            print(found)
            print(topic)
            self.path_found_topic.append(found)


    def path_callback_generator(self, i):
        print("entered call back generator")
        def callback(msg):
            print(f'in call back {i}')
            self.current_path[i] = []
            for pose in msg.poses:
                #self.get_logger().info(f'Received path {(pose.pose.position.x, pose.pose.position.y)}')
                self.current_path[i].append([pose.pose.position.x, pose.pose.position.y])
        
            print(f"drone{i} : {self.current_path}")
            
        print("returning callback")
        return callback
    
    def update_path_found_generator(self,i):
        def callback1(msg):
            
            #self.get_logger().info(f'path found {(msg.data)}')
            self.path_found_list[i]= msg.data
            print(self.path_found_list)
        return callback1
    

            
    # def update_path(self, i, msg):
    #     print(f'in call back {i}')
    #     self.current_path[i] = []
    #     for pose in msg.poses:
    #         self.get_logger().info(f'Received path {(pose.pose.position.x, pose.pose.position.y)}')
    #         self.current_path[i].append((pose.pose.position.x, pose.pose.position.y))
        
    #     print(self.current_path)

    # def update_path_found(self,i,msg):
    #     print("entered path found call back")
    #     self.path_found_list[i]=msg.data

    #     print(self.path_found_list)


    

    


        # self.get_logger().info(f'Received path {msg.poses}')
        # self.current_path[i] = []
        # for pose in msg.poses:
        #         self.current_path[i].append((pose.position.x, pose.position.y))
        # return self.path_callback(lambda msg,i: self.path_callback(msg))
    
        # self.current_path[index][0] = msg.poses.pose.position.x
        # self.current_path[index][1] = msg.poses.pose.position.y
        # print(self.current_path)

    


    def reset(self):
        self.swarm_.reset_estimators()


    def start(self):
        print("started")
        with Swarm(uris, factory=self.factory) as swarm:
            swarm.reset_estimators()
            print("reset done")
            self.swarm_ =swarm 
            swarm.parallel_safe(self.simple_log_async)
            swarm.parallel_safe(self.take_off)
            #self.setpoints_pickup_3(uris[0],uris[1],uris[2])
            #self.setpoints_pickup_2(uris[1],uris[2])
            #self.setpoints_pickup_1(uris[0])
            self.setpoints_pickup_1(uris[0],0,1.4)
            self.setpoints_pickup_1(uris[1],-1,-1)
            while(1):
                rclpy.spin_once(self)
                #self.list1 = self.setpoints_splitter()
                #print(self.list1)
                
                seq_=self.seq()
                swarm.parallel_safe(self.run_sequence, args_dict=seq_)
                #self.setpoints_pickup_1(uris[2])
                #swarm.parallel_safe(self.land)
    


    def log_stab_callback(self,scf,timestamp, data, logconf):
   
        self.x = float(data['stateEstimate.x'])
        self.y = float(data['stateEstimate.y'])
        self.vx = float(data['stateEstimate.vx'])
        self.vy = float(data['stateEstimate.vy'])
        
        self.position_data[scf] = [self.x,self.y,self.vx,self.vy,scf]
        # print("got data")
        #time.sleep(0.7)
        self.timer_callback()   
        

    def simple_log_async(self,scf):
        lg_stab = LogConfig(name='StateEstimate', period_in_ms=200)
        lg_stab.add_variable('stateEstimate.x', 'float')
        lg_stab.add_variable('stateEstimate.y', 'float')
        lg_stab.add_variable('stateEstimate.vx', 'float')
        lg_stab.add_variable('stateEstimate.vy', 'float')     
        print("added variables")
        cf=scf.cf
        cf.log.add_config(lg_stab)
        lg_stab.data_received_cb.add_callback(lambda t, d, l: self.log_stab_callback(cf.link_uri, t, d, l))
        lg_stab.start()
        #time.sleep(2)
        #lg_stab.stop()

    
    
    def activate_led_bit_mask(self,scf):
        scf.cf.param.set_value('led.bitmask', 255)
        print("light on")

    def deactivate_led_bit_mask(self,scf):
        scf.cf.param.set_value('led.bitmask', 0)
        print("light off")

    def light_check(self,scf):
        self.activate_led_bit_mask(scf)
        time.sleep(1)
        self.deactivate_led_bit_mask(scf)

    def take_off(self,scf):
        commander= scf.cf.high_level_commander
        commander.takeoff(1.0, 2.0)
        time.sleep(3)

    def land(self,scf):
        commander= scf.cf.high_level_commander
        commander.land(0.0, 2.0)
        time.sleep(2)
        commander.stop()
    
    # def setpoints(self):
    #     setpoints_list=[]
    #     for i in range(self.number_drones):
    #         setpoints_list.append([0,0])
    #         try:
    #             setpoints_list[i] = ([[self.position_data.get(uris[i])[0],self.position_data.get(uris[i])[1]]])
    #         except:
    #             setpoints_list[i] = ([[0,0]])
    #         for j in range (len(self.current_path[i])):
    #             setpoints_list[i].append(self.current_path[i][j])
    #             #print(setpoints_list)
    #     return setpoints_list

    def setpoints_splitter(self):
        distance_max=1
        distance_min=0.1
        results_list = []

        for i in range(self.number_drones):
            results_list.append([[self.position_data.get(uris[i])[0],self.position_data.get(uris[i])[1]]])
        print(f'result{results_list}')

        for i in range(self.number_drones):
            if self.path_found_list[i] == True:
                set_pts = self.current_path[i]
                print(set_pts)
                x = self.position_data.get(uris[i])[0]
                y = self.position_data.get(uris[i])[1]
                distance_setpoints_min= 100000
                for j in range(0,len(set_pts)):
                    distance_between_setpoint = (x-set_pts[j][0])**2 + (y-set_pts[j][1])**2
                    print(distance_between_setpoint)
                    if(distance_between_setpoint>distance_min**2 and distance_between_setpoint<distance_setpoints_min):
                        distance_setpoints_min=distance_between_setpoint
                        results_list[i]=[[set_pts[j][0],set_pts[j][1]]]
        print(f'updated list{results_list}')
        return results_list

                    


    




        # for i in range(len(setpoints_list)):
        #     set_pts=setpoints_list[i]
        #     #print(set_pts)
        #     if self.path_found_list[i] == True:
        #         update=1
        #         j=0
        #         while(update):
        #             update=0
        #             #for j in range(0,len(set_pts)-2):
        #             #print(set_pts[j+1])
        #             distance_between_setpoint = (set_pts[j][0]-set_pts[j+1][0])**2 + (set_pts[j][1]-set_pts[j+1][1])**2
        #             #print(distance_between_setpoint,i)
        #             if(distance_between_setpoint>distance_max**2):
        #                 new_setpoint = [(set_pts[j][0]+set_pts[j+1][0])/2, (set_pts[j][1]+set_pts[j+1][1])/2]
        #                 #print(new_setpoint)
        #                 set_pts.insert(j+1,new_setpoint)
        #                 j = 0
        #                 update = 1
        #             elif(distance_between_setpoint<distance_min**2):
        #                 #print(set_pts)
        #                 #print(f"poped eletement{set_pts[j+1]}")
        #                 x=set_pts.pop(j+1)
        #                 #print(x)
        #                 #print(set_pts)
        #                 update =1
        #             else:
        #                 set_pts = set_pts
        #                 #j = j+1
        #             #print(set_pts)
        #     else:
        #         continue



    def seq(self):   
        #drone_setpoint=setpoint_payload_3(i)
        #if(i==0):
            # drone_setpoint=pickup_2()
            # time=6.0
        # else:
            # drone_setpoint = setpoint_payload_2(drones_poistion,set_pts,i,d)
            # time= 2.0
        
        """
        sequence = [x,y,z,yaw,duration]
        x,y,z goto commands
        yaw angle of drone
        duration : time to reach setpoints
        """

        setpoints_list= self.setpoints_splitter()
        print("in seq")
        print(setpoints_list)
        duration = 10

        

        sequence0 = [
                (setpoints_list[0][0][0],setpoints_list[0][0][1] , 1,0, duration)
                ]

        sequence1 = [
            (setpoints_list[1][0][0],setpoints_list[1][0][1] , 1,0, duration)
            ]


        #sequence2 = [
        #    (drone_setpoint[4],drone_setpoint[5] , 1,drone_setpoint[6], time)
        #]
        seq_args = {

        uris[0]: [sequence0],
        uris[1]: [sequence1]
        #uris[2]: [sequence2]
    }
        return seq_args
    

    def run_sequence(self,scf: syncCrazyflie.SyncCrazyflie, sequence):
        cf = scf.cf


        for arguments in sequence:
            commander = scf.cf.high_level_commander


            x, y, z = arguments[0], arguments[1], arguments[2]
            yaw = arguments[3]
            duration = arguments[4]

            print('Setting position {} to cf {}'.format((x, y, z,yaw), cf.link_uri))
            #commander.set_default_velocity(0.2)
            commander.go_to(x, y, z, yaw, duration, relative=False)
            time.sleep(duration)


    def setpoints_pickup_3(self,uri_1,uri_2,uri_3):
        distance=0.30 # in meters centroid to drone
        #cx=set_pts[i][0] # x setpoint
        #cy=set_pts[i][1] # y setpoint
        cx=0
        cy=0
        y1= cy-(distance)*math.cos(math.pi/6) #drone1 y
        x1= cx-distance/2  # drone1 x
        y2= cy+(distance)*math.cos(math.pi/6) #drone2 y
        x2= cx-distance/2 #drone2 x

        y3= cy #drone 3 y
        x3 = cx+distance # drone 3 x
        #yaw=0 # angle of drone
        self.waypoint_data[uri_1]= [x1,y1]
        self.waypoint_data[uri_2]= [x2,y2]
        self.waypoint_data[uri_3]= [x3,y3]

    def setpoints_pickup_2(self,uri_1,uri_2):
        d=0.5 # distance in meters
        cx=0 #pickup coordinates in x
        cy=0 #pickup coordinates in y 
        x1=cx  # drone1 x
        x2=cx  # drone2 x
        y1=cy-d # drone1 y
        y2=cy+d # drone2 y
        yaw=0 # angle of drone
        self.waypoint_data[uri_1]= [x1,y1]
        self.waypoint_data[uri_2]= [x2,y2] 
    
    def setpoints_pickup_1(self,uri_1,cx,cy):
        x=cx
        y=cy
        self.waypoint_data[uri_1]= [x,y]





def main(args=None):


    rclpy.init(args=args)
    minimal_publisher = MinimalPublisher()




    print ("main")
    minimal_publisher.destroy_node()
    rclpy.shutdown()

if __name__ == '__main__':

    main()
