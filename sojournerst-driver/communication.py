

def calculate_checksum( data: bytes )->int:
    return (256 - (sum(list(data))%256))%256
