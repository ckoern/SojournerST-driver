import time 
import threading
import itertools  

import numpy as np

import serial 

from bokeh.models.sources import ColumnDataSource
from bokeh.plotting import figure, curdoc
from bokeh.layouts import column, row, layout, widgetbox, Spacer
from bokeh.palettes import Dark2_5 as palette


from bokeh.models import  TextInput, Button, CheckboxGroup

from packet import *

comport = "COM8"
ser = serial.Serial( comport, baudrate=115200, timeout=1 )
com_lock = threading.Lock()
#channel = CommandBankType(0) #either 0 or 1

data_source_ch0 = ColumnDataSource()
data_source_ch1 = ColumnDataSource()
start_time = time.time()


def send_command(cmd: CommandPacket, verbose = False):
    with com_lock:
        msg = cmd.put()
        if verbose:
            print(f"<< '{msg.hex()}'")    
        ser.write(msg)
        
        time.sleep(0.05)
        
        msg = ser.read(7)
        if verbose:
            print(f">> '{msg.hex()}'")
        response = ResponsePacket.load( msg, cmd.command_id.response_value_type)
        
        return response         

def get_value(cmd_id, channel):
        return send_command( CommandPacket( CommandScopeType.Channel,  CommandBankType(channel),cmd_id) ).response_value

def create_input(var):
    name, cmd_id = var
    if int(cmd_id) >= 0x30:
        default_value = get_value( ChannelCommandType( int(cmd_id)-32 ), 0 )
    else:
        default_value = ""
    val_input = TextInput(value=f"{default_value}", title=name)
    btn = Button(label = 'send', button_type = "warning", width = 100)
    def send_this_cmd():
        val =  cmd_id.command_value_type(val_input.value)
        for channel in checkbox_group.active:
            send_command(  CommandPacket( CommandScopeType.Channel, CommandBankType(channel), cmd_id, val ) )
    btn.on_click( send_this_cmd )


    return row(val_input, btn)

def create_read_figure( var, channel ):
    fig = figure(width=600, height=200)
    colors = itertools.cycle(palette)    
    if channel == 0:
        ds = data_source_ch0
    else:
        ds = data_source_ch1
    if type(var)== tuple:
        var = [var]
    for v,c in zip(var, colors):
        fig.line(x="time", y=v[0], source = ds, line_width=2, legend_label=v[0], color=c)
    fig.legend.location="left"
    return fig

variables = [("Target CPS", ChannelCommandType.channel_set_target_cps),
             ("PID Kp", ChannelCommandType.channel_pid_set_kp),
             ("PID Ki", ChannelCommandType.channel_pid_set_ki),
             ("PID Kd", ChannelCommandType.channel_pid_set_kd),
             ("PID Kn", ChannelCommandType.channel_pid_set_kn)
            ]

plot_variables = [ [ ("Current CPS", ChannelCommandType.channel_current_cps),
                     ("Target CPS", ChannelCommandType.channel_get_target_cps),
                     ("Setpoint Error", ChannelCommandType.channel_pid_setpoint_error),
                   ],
                   ("PID Integrator", ChannelCommandType.channel_pid_integrator_state ),
                   ("PID Differential", ChannelCommandType.channel_pid_filter_state)
                   ,
                   ("PID Kp", ChannelCommandType.channel_pid_get_kp),
                   ("PID Ki", ChannelCommandType.channel_pid_get_ki),
                   ("PID Kd", ChannelCommandType.channel_pid_get_kd)
 ]


def poll_data():
    dt = time.time() - start_time
    for channel in range(2):
        new_data = {"time": [dt] }
        for var in plot_variables:
            if type(var)== tuple:
                var = [var]
            for v in var:
                new_data[v[0]] = [ get_value(v[1], channel) ]
                #fig.line(x="time", y=v[0], source = data_source, line_width=2) 
        #new_data = { v: [get_value(vi)] for v,vi in plot_variables }
        if channel == 0:
            data_source_ch0.stream(new_data, rollover = 60*10)
        else:
            data_source_ch1.stream(new_data, rollover = 60*10)



empty_data = {"time": [] }
for var in plot_variables:
    if type(var)== tuple:
        var = [var]
    for v in var:
        empty_data[v[0]] = []
data_source_ch0.data =empty_data
data_source_ch1.data =dict(empty_data)

checkbox_group = CheckboxGroup(labels=["Motor 1", "Motor 2"], active=[0, 1])

rows = [ create_input(v) for v in variables ]

col = column(checkbox_group, *rows)
figs_ch0 = column( [create_read_figure(v, 0) for v in plot_variables] )
figs_ch1 = column( [create_read_figure(v, 1) for v in plot_variables] )

top_layput = row(col, figs_ch0, figs_ch1) 


for channel in range(2):
    send_command( CommandPacket( CommandScopeType.Channel, CommandBankType(channel), ChannelCommandType.channel_pid_set_kp, 0.001) ) 
    time.sleep(.1)
    send_command( CommandPacket( CommandScopeType.Channel, CommandBankType(channel), ChannelCommandType.channel_pid_set_ki, 0.002) ) 
    time.sleep(.1)
    send_command( CommandPacket( CommandScopeType.Channel, CommandBankType(channel), ChannelCommandType.channel_pid_set_kd, 0.0003) ) 
    time.sleep(.1)
    send_command( CommandPacket( CommandScopeType.Channel, CommandBankType(channel), ChannelCommandType.channel_pid_set_kn, 2) ) 



curdoc().add_root(top_layput)

curdoc().add_periodic_callback( poll_data, 1500 )

def cleanup_session(session_context):
    ser.close()

curdoc().on_session_destroyed(cleanup_session)