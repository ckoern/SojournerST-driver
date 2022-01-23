import serial
import sys
import time 
import struct 
import threading
import matplotlib.pyplot as plt 
import packet 

comport = sys.argv[1]
cmd_id =  packet.ChannelCommandType( int(sys.argv[2], 0) )
print(cmd_id)
cmd_val = cmd_id.command_value_type( sys.argv[3] )
channel = 0 


with serial.Serial(comport, baudrate=115200, timeout=1) as ser:
    def send(msg):
        print(f"<< '{msg.hex()}'")    
        ser.write(msg)
    
    def recv():
        msg = ser.read(7)
        print(f">> '{msg.hex()}'")
        return msg


    pkt = packet.CommandPacket( packet.CommandScopeType.Channel, packet.CommandBankType.Channel1, cmd_id, cmd_val )
    send(pkt.put() )
    resp = packet.ResponsePacket.load(recv(), cmd_id.response_value_type)
    print(resp, resp.response_value)