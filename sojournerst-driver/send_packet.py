import serial
import sys
import time 
import struct 
import threading
import matplotlib.pyplot as plt 
from packet import *

comport = sys.argv[1]

channel = CommandBankType(0) #either 0 or 1
com_lock = threading.Lock()
fig, ax = plt.subplots(5,1,figsize=(8,8), sharex=True)
fig.show()
plt.pause(1)
plotdata = [[],[],[],[],[], []]

def twos_complement(val):
    return (256 - (val%256))%256


with serial.Serial(comport, baudrate=115200, timeout=1) as ser:

        def send_command(cmd: CommandPacket, verbose = False):
            with com_lock:
                msg = cmd.put()
                if verbose:
                    print(f"<< '{msg.hex()}'")    
                ser.write(msg)
                
                time.sleep(0.04)
                
                msg = ser.read(7)
                if verbose:
                    print(f">> '{msg.hex()}'")
                response = ResponsePacket.load( msg, cmd.command_id.response_value_type)
                
                return response            

        def get_value(cmd_id):
            return send_command( CommandPacket( CommandScopeType.Channel, channel,cmd_id) ).response_value
        def update_loop():
            print("-------")
            v = send_command( CommandPacket( CommandScopeType.Channel, channel, ChannelCommandType.channel_pid_get_kp) ) #kp
            print(f"Current Kp: {v.response_value}")
            print("-------")
            time.sleep(.1)
            send_command( CommandPacket( CommandScopeType.Channel, channel, ChannelCommandType.channel_pid_set_kp, 0.001) ) 
            time.sleep(.1)
            send_command( CommandPacket( CommandScopeType.Channel, channel, ChannelCommandType.channel_pid_set_ki, 0.002) ) 
            time.sleep(.1)
            send_command( CommandPacket( CommandScopeType.Channel, channel, ChannelCommandType.channel_pid_set_kd, 0.0003) ) 
            time.sleep(.1)
            send_command( CommandPacket( CommandScopeType.Channel, channel, ChannelCommandType.channel_pid_set_kn, 2) ) 
            print("-------")
            time.sleep(1)
            v = send_command( CommandPacket( CommandScopeType.Channel, channel, ChannelCommandType.channel_pid_get_kp) ) #kp
            print(f"Current Kp: {v.response_value}")
            print("-------")
            time.sleep(1)

            
            print("-------")
            v =  get_target_cps()
            print(f"Current Target Cps: {v}")
            print("-------")
            time.sleep(0.1)
            v = get_value(ChannelCommandType.channel_current_cps)
            print(f"Current Measured Cps: {v}")
            print("-------")
            time.sleep(1)

            target_speed = 1234
            accel = 100

            while (True):
                target_speed *= -1
                accel *= -1
                for s in range(0,target_speed, accel):
                    print(f"Set Target Cps to {s}")
                    print("-------")
                    set_target_cps(s)
                    time.sleep(0.1)
                set_target_cps(target_speed)
                print(f"Set Target Cps to {target_speed}")
                print("-------")
                time.sleep(1)

                for i in range(10):
                    v = get_value(ChannelCommandType.channel_current_cps)
                    print(f"Current Measured Cps: {v}")
                    print("-------")
                    time.sleep(1)


                for s in range(target_speed, 0, -accel):
                    set_target_cps(s)
                    time.sleep(0.1)
                set_target_cps(0)
                print(f"Set Target Cps to 0")
                print("-------")
                time.sleep(1)

                for i in range(10):
                    v = get_value(ChannelCommandType.channel_current_cps)
                    print(f"Current Measured Cps: {v}")
                    print("-------")
                    time.sleep(1)

        def set_target_cps(val):
            send_command( CommandPacket( CommandScopeType.Channel, channel, ChannelCommandType.channel_set_target_cps, val) )
                


        def get_target_cps():
            return send_command( CommandPacket( CommandScopeType.Channel, channel, ChannelCommandType.channel_get_target_cps) ).response_value

        
        command_thread = threading.Thread(target=update_loop, daemon =True)
        command_thread.start()


        labels = ["Current Cps",
                    "Integrator",
                    "Filter",
                    "Gain",
                    "Setpoint Error"
        ]
        cmd_ids = [ ChannelCommandType.channel_current_cps,
                    ChannelCommandType.channel_pid_integrator_state,
                    ChannelCommandType.channel_pid_filter_state,
                    ChannelCommandType.channel_pid_gain,
                    ChannelCommandType.channel_pid_setpoint_error ]
        start = time.time()
        dt = []
        while(True):
            now = time.time()
            dt.append(now-start)
            for i in range(5):
                ax[i].clear()
                plotdata[i].append( get_value( cmd_ids[i]) ) 
                ax[i].plot(dt, plotdata[i], label = labels[i])
                ax[i].set_title(labels[i])
                ax[i].grid(True)
            target = get_target_cps()
            plotdata[-1].append(target)
            ax[0].plot(dt, plotdata[-1], label = "Target Cps")
            fig.tight_layout()
            fig.canvas.draw()
            plt.pause(0.02)

        
        
