import socket
import json

UDP_PORT = 5065


class UnityNetwork():

    def sendMovementData(self, dist_sum, pose_count, UDP_IP):
        sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        moveEvent = {
            "dist": round(dist_sum, 0),
            "pose_count": pose_count
        }        
        sock.sendto(json.dumps(moveEvent).encode(), (UDP_IP, UDP_PORT))
        #if(dist_sum > 0):
            #print(moveEvent)
