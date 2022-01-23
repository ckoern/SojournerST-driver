from enum import IntEnum
import struct
from typing import Union

import numpy as np 

import communication as com

class SyncError( RuntimeError ):
    pass 
class ChecksumError( RuntimeError ):
    pass 

class CommandScopeType(IntEnum):
    Global = 0
    Channel = 1


class CommandBankType(IntEnum):    
    Channel1 = 0
    Channel2 = 1

class IntAndTypesEnum(IntEnum):
    #multi-variables design per enum entry taken from https://stackoverflow.com/a/49926039

    def __new__(cls, value, command_type, response_type):
        obj = int.__new__(cls)
        obj._value_ = value
        return obj

    def __init__(self, value, command_value_type, response_value_type):
        # value already handled, ignore it
        self.command_value_type = command_value_type
        self.response_value_type = response_value_type

    def __int__(self):
        return self.value

class none_type(np.uint32):
    # custom type used for indicating when a command is either not requiring a 
    # command value or does not reply a response value
    # interally the standard uint32 is used and can influence
    # the checksum, but the exact value might be UB
    pass

class GlobalCommandType(IntAndTypesEnum):
    # --- global command scope ---
    global_foo_bar = 0x00, none_type, none_type 
    global_bar_baz = 0x01, none_type, none_type


class ChannelCommandType (IntAndTypesEnum):
    # --- channel command scope ---
    # this can collide with the global commands
    # they can be differentiated with the CommandScopeType bit

    # read only
    channel_current_cps = 0x00, none_type, np.float32
    channel_pid_integrator_state = 0x01, none_type, np.float32
    channel_pid_filter_state = 0x02, none_type, np.float32
    channel_pid_gain = 0x03, none_type, np.float32
    channel_pid_setpoint_error = 0x04, none_type, np.float32

    # r/w get commands
    channel_pid_get_kp = 0x10, none_type, np.float32
    channel_pid_get_ki = 0x11, none_type, np.float32
    channel_pid_get_kd = 0x12, none_type, np.float32
    channel_pid_get_kn = 0x13, none_type, np.float32
    channel_get_target_cps = 0x14, none_type, np.int32

    # write only 
    channel_stop = 0x20, none_type, none_type
    channel_pid_reset = 0x21, none_type, none_type

    # r/w set commands ids are offset by 32 (0x20) compared to the getters
    channel_pid_set_kp = 0x30, np.float32, none_type
    channel_pid_set_ki = 0x31, np.float32, none_type
    channel_pid_set_kd = 0x32, np.float32, none_type
    channel_pid_set_kn = 0x33, np.float32, none_type
    channel_set_target_cps = 0x34, np.int32, none_type
    
    


class ResponseType(IntEnum):
    Success = 0x01
    Error_Checksum = 0x81
    Error_Sync = 0x82
    Error_Value = 0x83
    Error_UnknownCommand = 0x84
    Error_Undefined = 0x85 # generic error


class CommandPacket:
    def __init__(self, scope: CommandScopeType, bank: CommandBankType, 
                 command_id: Union[GlobalCommandType, ChannelCommandType], 
                 command_value: Union[float, int, none_type, np.int32, np.uint32, np.float32, np.int16] = none_type(0), 
                 sync: int = 0xcc, checksum: int = None 
    ):
        self.scope = scope 
        self.bank = bank
        self.command_id = command_id
        self.sync = sync 

        # allow normal python types and cast them to the correct type 
        if  type(command_value) in [float, int]:
            command_value = command_id.command_value_type(command_value)
        # if a numpy datatype is used, it has to be correct
        elif command_id.command_value_type != type(command_value):
            raise ValueError( f"Given value is of type {type(command_value)} but {command_id.command_value_type} expected for command id {command_id}" )
        self.command_value = command_value

        if checksum is None:
            checksum = self.put()[-1]
        self.checksum = checksum

    def put(self)->bytes:
        b1 = int(self.scope) << 7
        b1 += int(self.bank) << 6
        b1 += int(self.command_id )
        msg = bytes( [self.sync, b1] )

        
        if type(self.command_value) == none_type:
            format_code = ">I"
        elif type(self.command_value) == np.int32:
            format_code = ">i"
        elif type(self.command_value) == np.uint32:
            format_code = ">I"
        elif type(self.command_value) == np.float32:
            format_code = ">f"
        else:
            raise ValueError(f"Invalid datatype: {type(self.command_value)}")

        msg += struct.pack(format_code, self.command_value)
        msg += bytes([com.calculate_checksum(msg)])
        return msg 


    @staticmethod
    def load(buffer:bytes)->'CommandPacket':
        if buffer[0] != 0xcc:
            raise SyncError(f"Initial Byte is 0x{buffer[0]:02x} (expected 0xcc)")

        if sum(buffer)%256 != 0:
            raise ChecksumError( f"Packet sum is {sum(buffer)%256} (expected 0)" )

        scope = CommandScopeType(buffer[1] >> 7)
        bank = CommandBankType( (buffer[1] >> 6)&0b01 )

        if scope == CommandScopeType.Global:
            command_id = GlobalCommandType( buffer[1] & 0x3f ) # lower 6 bits
        else:
            command_id = ChannelCommandType( buffer[1] & 0x3f ) # lower 6 bits
        
        
        if  command_id.command_value_type == none_type:
            format_code = ">I"
        elif command_id.command_value_type == np.float32:
            format_code = ">f"
        elif command_id.command_value_type == np.int32:
            format_code = ">i"
        elif command_id.command_value_type == np.uint32:
            format_code = ">I"
        else:
            raise ValueError(f"Invalid datatype: { command_id.command_value_type}")

        command_value = struct.unpack(format_code, buffer[2:6])[0]
        command_value = command_id.command_value_type(command_value)
        return CommandPacket(scope, bank, command_id, command_value, sync = buffer[0], checksum=buffer[-1])



class ResponsePacket():
    def __init__(self, cmd_checksum: int, response_type: ResponseType,
                 response_value: Union[none_type, np.int32, np.uint32, np.float32, np.int16], 
                 checksum: int = None
    ):
        self.cmd_checksum = cmd_checksum
        self.response_type = response_type
        self.response_value = response_value
        if checksum is None:
            checksum = self.put()[-1]
        self.checksum = checksum

    def put(self)->bytes:
        msg = bytes([self.cmd_checksum, int(self.response_type) ]) 
        if type(self.response_value) == np.int32:
            format_code = ">i"
        elif type(self.response_value) == np.uint32:
            format_code = ">I"
        elif type(self.response_value) == np.float32:
            format_code = ">f"
        elif type(self.response_value) ==none_type:
            format_code = ">I"
        else:
            raise ValueError(f"Invalid datatype: { type(self.response_value)}")

        msg += struct.pack(format_code, self.response_value)
        msg += bytes([com.calculate_checksum(msg)])
        return msg


    @staticmethod
    def load(buffer: bytes, 
             datatype: Union[none_type, np.int32, np.uint32, np.float32, np.int16]
    ) -> "ResponsePacket":
        
        if sum(buffer)%256 != 0:
            raise ChecksumError( f"Packet sum is {sum(buffer)%256} (expected 0)" )

        cmd_checksum = buffer[0]
        response_type = ResponseType(buffer[1])
        if datatype ==none_type:
            format_code = ">I"
        elif datatype == np.float32:
            format_code = ">f"
        elif datatype == np.int32:
            format_code = ">i"
        elif datatype == np.uint32:
            format_code = ">I"
        else:
            raise ValueError(f"Invalid datatype: {datatype}")
        response_value = datatype( struct.unpack(format_code, buffer[2:6])[0] )
        
        return ResponsePacket( cmd_checksum, response_type, response_value, checksum=buffer[-1] )


