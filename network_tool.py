import socket

UDP_IP = "192.168.178.39"
UDP_PORT = 5065


class UnityNetwork():

    def sendMovementData(self, dist_sum):
        sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        data_string = "move_"+str(round(dist_sum, 0))
        sock.sendto(data_string.encode(), (UDP_IP, UDP_PORT))
        #print(data_string)

    def sendPosesData(self, posecount):
        sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        data_string = "poses_"+str(round(posecount, 0))
        sock.sendto(data_string.encode(), (UDP_IP, UDP_PORT))
        #print(data_string)
