import can
import threading
import time
import random
import socket
import struct


send_lock = threading.Lock()

gear = 0  # 0 = park, 1 = reverse, 2 = neutral, 3 = drive
rpm = 0  # Initialize RPM to 0
speed = 0 # in meters per second

# Define the messages for 20ms interval
messages_20ms = [
    (0x19E, [0x00, 0xE0, 0xB3, 0xFC, 0xF0, 0x43, 0x00, 0x00]),
    (0x0AA, [0x5F, 0x59, 0xFF, 0x00, 0x34, 0x0D, 0x80, 0x99])
]

# Define the messages for 100ms interval
messages_100ms = [
    (0x1D2, [0xE1, 0x0C, 0x8F, 0x0D, 0xF0]),
    (0x1a6, [0x00,0x00,0x00,0x00,0x00,0x00,0x00,0x00])
    # Add more messages as needed
]

def send_messages_20ms(bus):
    while True:
        for message_id, data in messages_20ms:
            # Wait for 1ms before sending the message
            time.sleep(0.001)

            # Acquire the lock before sending a message
            send_lock.acquire()

            # Generate a random value for the last byte (0x00-0xFF)
            data[-1] = random.randint(0x00, 0xFF)

            value = padhexa(hex(int(rpm) * 4))
            if message_id == 0x0AA:
                data[5] = int(value[2:4], 16)
                data[4] = int(value[4:6], 16)
            if message_id == 0x19E:
                # Update the 3rd byte using the equation
                data[2] = ((((data[2] >> 4) + 3) << 4) & 0xF0) | 0x03

            message = can.Message(arbitration_id=message_id, data=data, is_extended_id=False)
            bus.send(message, timeout=1)
            #print("Sent message (20ms):", message)

            # Release the lock after sending the message
            send_lock.release()

        # Wait for 20ms
        time.sleep(0.02)


def send_messages_100ms(bus):
    gearCounter = 0x0D

    while True:
        for message_id, data in messages_100ms:
            # Wait for 1ms before sending the message
            time.sleep(0.001)

            # Acquire the lock before sending a message
            send_lock.acquire()

            if message_id == 0x1D2:
                # Update the counter
                gearCounter += 0x10

                # Check if the counter reaches 0xED
                if gearCounter == 0xED:
                    # Reset the counter to 0x0D
                    gearCounter = 0x0D

                # Update the counter value at data[3]
                data[3] = gearCounter

            if message_id == 0x1A6:
                can_send_speed(bus)  # Call the can_send_speed function here
            # Update the gear value
            match gear:
                case 0:
                    data[0] = 0xE1
                case 1:
                    data[0] = 0xD2
                case 2:
                    data[0] = 0xB4
                case 3:
                    data[0] = 0x78
                case _:
                    print("Invalid gear")

            message = can.Message(arbitration_id=message_id, data=data, is_extended_id=False)
            bus.send(message, timeout=1)
            #print("Sent message (100ms):", message)

            # Release the lock after sending the message
            send_lock.release()

        # Wait for 100ms
        time.sleep(0.1)


def receive_messages(bus):
    while True:
        message = bus.recv()
        #print("Received message:", message)

last_speed_value = 0

def can_send_speed(bus):
    global last_speed_value
    delta_time = 100  # Time difference in milliseconds
    speed_value = int(speed * 3.6) + last_speed_value
    speed_frame = messages_100ms[1][1]
    counter = ((speed_frame[6] << 8) | speed_frame[7]) & 0x0FFF
    counter += int(delta_time * 3.14159)

    speed_frame[0] = speed_value & 0xFF
    speed_frame[1] = (speed_value >> 8) & 0xFF

    speed_frame[2] = speed_frame[0]
    speed_frame[3] = speed_frame[1]

    speed_frame[4] = speed_frame[0]
    speed_frame[5] = speed_frame[1]

    speed_frame[6] = counter & 0xFF
    speed_frame[7] = ((counter >> 8) & 0xFF) | 0xF0
    # Pack the speed frame into a struct
    data = struct.pack('B' * 8, *speed_frame)
    print(data)
    # Create a CAN message
    message = can.Message(arbitration_id=0x1a6, data=speed_frame, is_extended_id=False)

    # Send the message via the CAN bus
    bus.send(message, timeout=1)

    # Update the last speed value
    last_speed_value = speed_value

def padhexa(s):
    return '0x' + s[2:].zfill(4)


def connect_to_game_socket():
    # Connect to the game socket
    sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    sock.bind(('127.0.0.1', 4444))

    # Receive data from the game and update variables accordingly
    while True:
        global rpm
        global speed
        # Receive data.
        data, _ = sock.recvfrom(256)

        if not data:
            break  # Lost connection

        # Unpack the data.
        outgauge_pack = struct.unpack('I4sH2c7f2I3f16s16si', data)
        time_value = outgauge_pack[0]
        car = outgauge_pack[1]
        flags = outgauge_pack[2]
        gear = outgauge_pack[3]
        speed = outgauge_pack[5]
        rpm = outgauge_pack[6]
        turbo = outgauge_pack[7]
        engtemp = outgauge_pack[8]
        fuel = outgauge_pack[9]
        oilpressure = outgauge_pack[10]
        oiltemp = outgauge_pack[11]
        dashlights = outgauge_pack[12]
        showlights = outgauge_pack[13]
        throttle = outgauge_pack[14]
        brake = outgauge_pack[15]
        clutch = outgauge_pack[16]
        display1 = outgauge_pack[17]
        display2 = outgauge_pack[18]


        # Add your code here to update other variables if needed
        # For example:
        # speed_kph = speed * 3.6  # Convert speed to km/h
        # fuel_percentage = fuel * 100  # Convert fuel to percentage

    # Close the socket connection
    sock.close()



# Create a CAN bus object
bus = can.interface.Bus(channel='com9', bustype='seeedstudio', bitrate=500000)

# Create threads for sending and receiving messages
send_thread_20ms = threading.Thread(target=send_messages_20ms, args=(bus,))
send_thread_100ms = threading.Thread(target=send_messages_100ms, args=(bus,))
receive_thread = threading.Thread(target=receive_messages, args=(bus,))
game_socket_thread = threading.Thread(target=connect_to_game_socket)

# Start the sending, receiving, and game socket threads
send_thread_20ms.start()
send_thread_100ms.start()
receive_thread.start()
game_socket_thread.start()


# Wait for the threads to finish
send_thread_20ms.join()
send_thread_100ms.join()
receive_thread.join()
game_socket_thread.join()

# Shutdown the CAN bus
bus.shutdown()
