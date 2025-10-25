# AllStartLink Hub Demonstration Program
# Copyright (C) 2025, Bruce MacKinnon KC1FSZ
#
# This program is free software: you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with this program.  If not, see <https://www.gnu.org/licenses/>.
#
# FOR AMATEUR RADIO USE ONLY.
# NOT FOR COMMERCIAL USE WITHOUT PERMISSION.
#
# Overview
# --------
# This program provides a simple implementation of an AllStarLink 
# hub. The goal is to demonstrate AllStarLink functionaltion without
# dependency on the Asterisk infrastructure.
#
import time
import requests
import socket
import random
from enum import Enum
import base64
from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.asymmetric import padding
from cryptography.hazmat.primitives import serialization
from scipy.signal import firwin, lfilter, lfilter_zi
import numpy as np
# TODO: THIS IS DEPRECATED AS OF PYTHON 3.13, NEED TO REPLACE
import audioop
import alsaaudio
import struct 

# ===========================================================================
# USER CONFIGURATION AREA - PLEASE CUSTOMIZE HERE
#
# Put in your AllStarLink node ID here:
node_id = "61057"
# Put in your node password here:
node_password = "xxxxxx"
# Name of ALSA audio device used for output
audio_device_name = "default"
# ===========================================================================

# ===========================================================================
# System configurations that normally shouldn't need to change:
#
# The UDP port that the server listens on for IAX2 traffic.
iax2_port = 4569
# The interface that the server binds on. 0.0.0.0 means all interfaces.
UDP_IP = "0.0.0.0" 
# The AllStarLink registration server
reg_url = "https://register.allstarlink.org"
# The RSA public key is provided in the ASL3 installation. On the Pi
# appliance distribution it is located at:
#   /usr/share/asterisk/keys/allstar.pub
# The public key is in PEM format:
public_key_pem = "-----BEGIN PUBLIC KEY-----\n\
MIGfMA0GCSqGSIb3DQEBAQUAA4GNADCBiQKBgQCu3h0BZQQ+s5kNM64gKxZ5PCpQ\n\
9BVzhl+PWVYXbEtozlJVVs1BHpw90GsgScRoHh4E76JuDYjEdCTuAwg1YkHdrPfm\n\
BUjdw8Vh6wPFmf3ozR6iDFcps4/+RkCUb+uc9v0BqZIzyIdpFC6dZnJuG5Prp7gJ\n\
hUaYIFwQxTB3v1h+1QIDAQAB\n\
-----END PUBLIC KEY-----\n"
# Interval between registrations (in milliseconds)
reg_interval_ms = 5 * 60 * 1000
# ===========================================================================

def is_full_frame(frame):
    return frame[0] & 0b10000000 == 0b10000000

def is_mini_voice_packet(frame):
    return frame[0] & 0b10000000 == 0b00000000

def get_full_source_call(frame):
    return ((frame[0] & 0b01111111) << 8) | frame[1]

def get_full_r_bit(frame):
    return frame[2] & 0b10000000 == 0b10000000

def get_full_dest_call(frame):
    return ((frame[2] & 0b01111111) << 8) | frame[3]

def get_full_timestamp(frame):
    return (frame[4] << 24) | (frame[5] << 16) | (frame[6] << 8) | frame[7]

def get_full_outseq(frame):
    return frame[8]

def get_full_inseq(frame):
    return frame[9]

def get_full_type(frame):
    return frame[10]

def get_full_subclass_c_bit(frame):
    return frame[11] & 0b10000000 == 0b10000000

def get_full_subclass(frame):
    return frame[11] & 0b01111111

def make_call_token():
    # TODO: RANDOMIZE
    return "1759883232?e4b9017e102c1f831e6db6ab1bc85ebce1ea240e".encode("utf-8")

def make_information_element(id: int, content):
    result = bytearray()
    result += id.to_bytes(1, byteorder='big')
    result += len(content).to_bytes(1, byteorder='big')
    result += content
    return result

def encode_information_elements(ie_map: dict): 
    result = bytearray()
    for key in ie_map.keys():
        if not isinstance(key, int):
            raise Exception("Type error")
        result += make_information_element(key, ie_map[key])
    return result

def decode_information_elements(data: bytes):
    """
    Takes a byte array containing zero or more information elements
    and unpacks it into a dictionary. The key of the dictionary is 
    the integer element ID and the value of the dictionary is a byte
    array with the content of the element.
    """
    result = dict()
    state = 0
    working_id = 0
    working_length = 0
    working_data = None
    # Cycle across all data
    for b in data:
        if state == 0:
            working_id = b
            state = 1
        elif state == 1:
            working_length = b 
            working_data = bytearray()
            if working_length == 0:
                result[working_id] = working_data
                state = 0
            else:
                state = 2
        elif state == 2:
            working_data.append(b)
            if len(working_data) == working_length:
                result[working_id] = working_data
                state = 0
        else:
            raise Exception()
    # Sanity check - we should end in the zero state
    if state != 0:
        raise Exception("Data format error")
    return result

def is_NEW_frame(frame):
    return is_full_frame(frame) and \
        get_full_type(frame) == 6 and \
        get_full_subclass_c_bit(frame) == False and \
        get_full_subclass(frame) == 1

def is_ACK_frame(frame):
    return is_full_frame(frame) and \
        get_full_type(frame) == 6 and \
        get_full_subclass_c_bit(frame) == False and \
        get_full_subclass(frame) == 4

def is_HANGUP_frame(frame):
    return is_full_frame(frame) and \
        get_full_type(frame) == 6 and \
        get_full_subclass_c_bit(frame) == False and \
        get_full_subclass(frame) == 5

def is_LAGRQ_frame(frame):
    return is_full_frame(frame) and \
        get_full_type(frame) == 6 and \
        get_full_subclass_c_bit(frame) == False and \
        get_full_subclass(frame) == 11

def is_PING_frame(frame):
    return is_full_frame(frame) and \
        get_full_type(frame) == 6 and \
        get_full_subclass_c_bit(frame) == False and \
        get_full_subclass(frame) == 2

def is_VOICE_frame(frame):
    return is_full_frame(frame) and \
        get_full_type(frame) == 2 and \
        get_full_subclass_c_bit(frame) == False and \
        get_full_subclass(frame) == 4

def make_frame_header(source_call: int, dest_call: int, timestamp: int, 
    out_seq: int, in_seq: int, frame_type: int, frame_subclass: int):
    result = bytearray()
    result += source_call.to_bytes(2, byteorder='big')
    result[0] = result[0] | 0b10000000
    result += dest_call.to_bytes(2, byteorder='big')
    result[2] = result[2] & 0b01111111
    result += timestamp.to_bytes(4, byteorder='big')
    result += out_seq.to_bytes(1, byteorder='big')
    result += in_seq.to_bytes(1, byteorder='big')
    # Type
    result += int(frame_type).to_bytes(1, byteorder='big')
    # Subclass
    result += int(frame_subclass).to_bytes(1, byteorder='big')
    return result

def make_CALLTOKEN_frame(source_call: int, dest_call: int, timestamp: int, 
    out_seq: int, in_seq: int, token):
    result = make_frame_header(source_call, dest_call, timestamp, out_seq, in_seq,
        6, 40)
    result += encode_information_elements({ 54: token })
    return result

def make_ACK_frame(source_call: int, dest_call: int, timestamp: int,
    out_seq: int, in_seq: int):
    result = make_frame_header(source_call, dest_call, timestamp, out_seq, in_seq,
        6, 4)
    return result

def make_AUTHREQ_frame(source_call: int, dest_call: int, timestamp: int,
    out_seq: int, in_seq: int, challenge: str):
    result = make_frame_header(source_call, dest_call, timestamp, out_seq, in_seq,
        6, 8)
    # Information elements
    result += encode_information_elements({ 
        14: int(4).to_bytes(2, byteorder='big'),
        15: challenge.encode("utf-8"), 
        6: "allstar-sys".encode("utf-8") 
    })
    return result

def make_ACCEPT_frame(source_call: int, dest_call: int, timestamp: int,
    out_seq: int, in_seq: int):
    result = make_frame_header(source_call, dest_call, timestamp, out_seq, in_seq,
        6, 7)
    # Information elements
    result += encode_information_elements({ 
        9: int(4).to_bytes(4, byteorder='big'),
        56: b'\x00\x00\x00\x00\x00\x00\x00\x00\x04'
    })
    return result

def make_RINGING_frame(source_call: int, dest_call: int, timestamp: int,
    out_seq: int, in_seq: int):
    return make_frame_header(source_call, dest_call, timestamp, out_seq, in_seq, 4, 3)

def make_ANSWER_frame(source_call: int, dest_call: int, timestamp: int,
    out_seq: int, in_seq: int):
    return make_frame_header(source_call, dest_call, timestamp, out_seq, in_seq, 4, 4)

def make_STOP_SOUNDS_frame(source_call: int, dest_call: int, timestamp: int,
    out_seq: int, in_seq: int):
    return make_frame_header(source_call, dest_call, timestamp, out_seq, in_seq, 4, 255)

def make_LAGRP_frame(source_call: int, dest_call: int, timestamp: int,
    out_seq: int, in_seq: int):
    return make_frame_header(source_call, dest_call, timestamp, out_seq, in_seq, 6, 12)

def make_PONG_frame(source_call: int, dest_call: int, timestamp: int,
    out_seq: int, in_seq: int):
    return make_frame_header(source_call, dest_call, timestamp, out_seq, in_seq, 6, 3)

def make_VOICE_frame(source_call: int, dest_call: int, timestamp: int,
    out_seq: int, in_seq: int, audio_block: bytes):
    result = make_frame_header(source_call, dest_call, timestamp, out_seq, in_seq,
        2, 4)
    result += audio_block
    return result

def make_VOICE_miniframe(source_call: int, timestamp: int, audio_data: bytes):
    result = bytearray()
    result += source_call.to_bytes(2, byteorder='big')
    # Make sure the top bit is zero (indicates mini-frame)
    result[0] = result[0] & 0b01111111
    # Per RFC 5456 section 8.1.2: the timestamp on a mini-frame is 
    # just the lower 16 bits
    full_32bit_stamp = timestamp.to_bytes(4, byteorder='big')
    result.append(full_32bit_stamp[2])
    result.append(full_32bit_stamp[3])
    result += audio_data
    return result

def encode_ulaw(pcm_data):
    # TODO: REMOVE DEPENDENCY ON THIS DEPRECATED LIBRARY
    return audioop.lin2ulaw(pcm_data, 2)

def decode_ulaw(g711_data: bytes):
    # TODO: REMOVE DEPENDENCY ON THIS DEPRECATED LIBRARY
    # Testing has shown that this created little-endian integers
    b = audioop.ulaw2lin(g711_data, 2)
    return struct.unpack(f'<{160}h', b)

def current_ms():
    return int(time.time() * 1000)

def current_ms_frac():
    return time.time() * 1000

public_key = serialization.load_pem_public_key(public_key_pem.encode("utf-8"))

# ALSA audio hardware setup
# Note everything here runs at 48kHz. One block is 960 samples.
audio_device_play = alsaaudio.PCM(channels=1, rate=48000, format=alsaaudio.PCM_FORMAT_S16_LE, 
    periodsize=160*6, device=audio_device_name)
audio_device_capture = alsaaudio.PCM(alsaaudio.PCM_CAPTURE, alsaaudio.PCM_NONBLOCK,
    channels=1, rate=48000, format=alsaaudio.PCM_FORMAT_S16_LE, 
    periodsize=160*6, device=audio_device_name)

# FIR filter used for resampling
# Please see https://mackinnon.info/2025/10/24/asl-usb-audio.html
sample_rate = 48000
nyq_rate = sample_rate / 2.0
# The cutoff frequency of the filters, determined from looking at the
# ASL coefficients and backing into the approximate value.
lpf_cutoff_hz = 4300
lpf_N = 31
lpf_beta = 3.0
# Use a Kaiser window to create a lowpass FIR filter:
lpf_taps = firwin(lpf_N, lpf_cutoff_hz / nyq_rate, window=('kaiser', lpf_beta))

# The zi object is used to maintain the state inside of the
# FIR since we are applying data one block at a time. State is important
# to maintain continuity between blocks.
us_lpf_zi = lfilter_zi(lpf_taps, [1])

# Changes 8K audio to 48K audio
def upsample(pcm_data_8k):
    global us_lpf_zi
    pcm_data_48k = []
    # First do the 1:6 expansion
    for s in pcm_data_8k:
        for i in range(0,6):
            pcm_data_48k.append(s)
    # Apply the LPF to the expanded data to prevent aliasing
    # NOTE: zi is being passed around each time to maintain state
    pcm_data_48k, us_lpf_zi = lfilter(lpf_taps, [1.0], pcm_data_48k, zi=us_lpf_zi)
    return pcm_data_48k

# The zi object is used to maintain the state inside of the
# FIR since we are applying data one block at a time.
ds_lpf_zi = lfilter_zi(lpf_taps, [1])

# Changes 48K audio to 8K audio
# TODO: Use a more efficient decimation filter
def downsample(pcm_data_48k):
    global ds_lpf_zi
    # Apply the LPF to the expanded data to prevent aliasing
    # NOTE: zi is being passed around each time to maintain state
    pcm_data_48k, ds_lpf_zi = lfilter(lpf_taps, [1.0], pcm_data_48k, zi=ds_lpf_zi)
    pcm_data_8k = []
    # Do the 6:1 decimation
    i = 0
    for j in range(0, 160):
        pcm_data_8k.append(pcm_data_48k[i])
        i += 6
    return pcm_data_8k

# TODO: Look at struct.pack()
def make_s16_le(data):
    result = bytearray()
    for d in data:
        i = int(d) 
        low = i & 0xff
        high = (i >> 8) & 0xff
        result.append(low)
        result.append(high)
    return result

call_id_counter = 1
last_reg_ms = 0
first_tick_ms = current_ms()
tick_counter = 0

class State(Enum):
    IDLE = 1
    NEW1 = 2 
    NEW2 = 3
    RINGING = 4
    IN_CALL = 5

state = State.IDLE
state_source_call_id = 0
state_call_id = 0
state_call_start_ms = 0
state_call_start_stamp = 0
state_challenge = ""
state_expected_inseq = 0
state_outseq = 0
state_voice_sent_count = 0

# Audio packets received
audio_capture_queue = []

# Structures used for communicating with the registration server
reg_node_msg = {
    "node": node_id,
    "passwd": node_password,
    "remote": 0
}
reg_msg = {
    # TODO: Understand this port
    "port": 7777,
    "data": {
        "nodes": {
        }
    }
}
reg_msg["data"]["nodes"][node_id] = reg_node_msg

# Create a UDP socket and bind 
sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
sock.bind((UDP_IP, iax2_port))
# This prevents the recvfrom() call below from blocking forever. 
sock.setblocking(False)

print(f"Listening on IAX2 port {UDP_IP}:{iax2_port}")

# ---- Main event loop -----------------------------------------------------

while True:

    # A tick cycle happens every 20ms. There are some special activities
    # that can happen in a tick cycle.
    is_tick_cycle = False
    now = current_ms_frac()
    if now >= first_tick_ms + tick_counter * 20:
        is_tick_cycle = True
        tick_counter += 1

    # Pull in local audio no matter what (non-blocking) to keep the hardware
    # queues clear.
    audio_in_l, audio_in_data = audio_device_capture.read()
    # If we are in a call this audio packet is queued for later delivery to 
    # the network.
    if state == State.IN_CALL:
        if audio_in_l > 0:
            audio_capture_queue.append(audio_in_data)

    # Process any timer-based activity

    # Periodically register the node so that other peers known where to find us
    if (current_ms() - last_reg_ms) > reg_interval_ms:
        reg_response = requests.post(reg_url, json=reg_msg)
        print("Registration response:", reg_response.text)
        last_reg_ms = current_ms()

    if state == State.RINGING:

        # Look for timeout on the ringer
        if current_ms() > state_timeout:

            resp = make_ANSWER_frame(state_call_id, 
                state_source_call_id,
                state_call_start_ms + (current_ms() - state_call_start_stamp),
                state_outseq, 
                state_expected_inseq)
            print("Sending ANSWER", resp, state_outseq, state_expected_inseq)
            sock.sendto(resp, addr)
            state_outseq += 1

            resp = make_STOP_SOUNDS_frame(state_call_id, 
                state_source_call_id,
                state_call_start_ms + (current_ms() - state_call_start_stamp),
                state_outseq, 
                state_expected_inseq)
            print("Sending STOP_SOUNDS", resp, state_outseq, state_expected_inseq)
            sock.sendto(resp, addr)
            state_outseq += 1

            state = State.IN_CALL

    # If we are in an active call and there is audio waiting to be delievered out
    # to the network then send it now.
    if state == State.IN_CALL:

        # TODO: CONFIGURABLE DEPTH BEFORE WE ALLOW SERVICING?
        if is_tick_cycle and len(audio_capture_queue) > 0:
            # Pull the oldest auto block
            audio_in_data = audio_capture_queue.pop(0)
            assert(len(audio_in_data) == 160 * 6 * 2)
            # Convert the data into PCM numbers. The hardware
            # is running at 48K so there are 160 * 6 samples.
            # The audio device uses little-endian.
            audio_in_pcm_48k = struct.unpack(f'<{960}h', audio_in_data)
            # Downsample 48k->8k
            audio_in_pcm_8k = downsample(audio_in_pcm_48k)
            assert(len(audio_in_pcm_8k) == 160)
            # Convert from numbers into S16_LE format
            audio_in_s16le_8k = make_s16_le(audio_in_pcm_8k)
            assert(len(audio_in_s16le_8k) == 160 * 2)
            # Convert to G711 format
            audio_in_ulaw = encode_ulaw(audio_in_s16le_8k)
            assert(len(audio_in_ulaw) == 160)

            # TODO: THIS LOGIC NEEDS TO BE IMPROVED. THE FULL VOICE
            # FRAME SHOULD BE SENT WHENEVER THE 16-BIT TIMESTAMP ROLLS.
            if state_voice_sent_count == 0:
                # For the first audio frame, make a full voice frame. 
                resp = make_VOICE_frame(state_call_id, 
                    state_source_call_id,
                    state_call_start_ms + (current_ms() - state_call_start_stamp),
                    state_outseq, 
                    state_expected_inseq,
                    audio_in_ulaw)
                print("Sending VOICE", resp, state_outseq, state_expected_inseq)
                sock.sendto(resp, addr)
                state_outseq += 1
            # After the first we can use mini-frames.
            else:
                resp = make_VOICE_miniframe(state_call_id, 
                    state_call_start_ms + (current_ms() - state_call_start_stamp),
                    audio_in_ulaw)
                sock.sendto(resp, addr)

            state_voice_sent_count += 1

    # Look for new network messages from the peer (non-blocking)
    try:
        frame, addr = sock.recvfrom(1024)
    except BlockingIOError:
        continue

    # Generic processing of full frames (regardless of state)
    if is_full_frame(frame):

        print("---------------------------------------")
        if is_ACK_frame(frame):
            print(f"ACK from {addr}")
        elif is_NEW_frame(frame):
            print(f"NEW from {addr}")
        else:    
            print(f"Full Frame from {addr}")        
        print("R", get_full_r_bit(frame), "Source", get_full_source_call(frame), "Dest", get_full_dest_call(frame))
        print("Oseqno", get_full_outseq(frame), "Iseqno", get_full_inseq(frame))
        print("Type", get_full_type(frame), "Subclass", get_full_subclass(frame))

        # ---------------------------------------------------------------------
        # Deal with the inbound sequence number tracking

        # When a NEW is received the inbound sequence counter is reset.
        if is_NEW_frame(frame):
            state_expected_inseq = 1
            state_outseq = 0

        # When an ACK is received we can validate its OSeqno, but we don't move 
        # the expectation forward since the sender isn't incrementing their sequence
        # for an ACK.
        elif is_ACK_frame(frame):
            if not get_full_r_bit(frame):
                if  get_full_outseq(frame) != state_expected_inseq:
                    print("WARNING: Inbound sequence error")

        # For all other frames we validate the sequence number
        # and then move our expectation forward.
        else:
            if not get_full_r_bit(frame):
                if  get_full_outseq(frame) != state_expected_inseq:
                    print("WARNING: Inbound sequence error")
                # Pay attention to wrap
                state_expected_inseq = (get_full_outseq(frame) + 1) % 256

    # ---------------------------------------------------------------------
    # State-independent message processing

    # When an ACK is processed there's nothing left to do with it
    if is_ACK_frame(frame):
        continue

    # Deal with LAGRQ messages by sending a LAGRP
    elif is_LAGRQ_frame(frame):
        resp = make_LAGRP_frame(state_call_id, 
            state_source_call_id,
            get_full_timestamp(frame),
            state_outseq, 
            state_expected_inseq)                
        print("Sending LAGRP", resp, state_outseq, state_expected_inseq)
        state_outseq += 1
        sock.sendto(resp, addr)
        # Nothing left to do with this
        continue

    # Deal with PING messages by sending a PONG
    elif is_PING_frame(frame):
        resp = make_PONG_frame(state_call_id, 
            state_source_call_id,
            state_call_start_ms + (current_ms() - state_call_start_stamp),
            state_outseq, 
            state_expected_inseq)                
        print("Sending PONG", resp, state_outseq, state_expected_inseq)
        state_outseq += 1
        sock.sendto(resp, addr)
        # Nothing left to do with this
        continue

    # ---------------------------------------------------------------------
    # State-dependent message processing
  
    if state == State.IDLE:
        if is_NEW_frame(frame):
            # Get call start information
            state_source_call_id = get_full_source_call(frame)
            state_call_start_stamp = current_ms()
            state_call_start_ms = get_full_timestamp(frame)
            state_voice_sent_count = 0
            # Send a CALLTOKEN challenge
            state_token = make_call_token()
            # NOTE: For now the call ID is set to 1
            resp = make_CALLTOKEN_frame(1, 
                state_source_call_id,
                state_call_start_ms + (current_ms() - state_call_start_stamp),
                state_outseq, 
                state_expected_inseq,                
                state_token)
            print("Sending CALLTOKEN", resp, state_outseq, state_expected_inseq)
            state_outseq += 1
            sock.sendto(resp, addr)
            state = State.NEW1
        else:
            print("Ignoring unknown message (IDLE)")

    # In this state we are waiting for a NEW with the right CALLTOKEN
    elif state == State.NEW1:
        if is_NEW_frame(frame):

            # Decode the information elements
            ies = decode_information_elements(frame[12:])

            # Make sure we have the right token
            if get_full_source_call(frame) == state_source_call_id and \
                54 in ies and \
                ies[54] == state_token:

                # Generate the unique ID for this call
                state_call_id = call_id_counter
                call_id_counter += 1
                # Generate the authentication challenge data
                state_challenge = "{:09d}".format(random.randint(1,999999999))

                print("Got expected token, starting call", state_call_id)

                # Send ACK
                resp = make_ACK_frame(state_call_id, 
                    state_source_call_id,
                    state_call_start_ms + (current_ms() - state_call_start_stamp),
                    state_outseq, 
                    state_expected_inseq)
                print("Sending ACK", resp, state_outseq, state_expected_inseq)
                sock.sendto(resp, addr)
                # IMPORTANT: We don't move the outseq forward!

                # Send AUTHREQ
                resp = make_AUTHREQ_frame(state_call_id, 
                    state_source_call_id,
                    state_call_start_ms + (current_ms() - state_call_start_stamp),
                    state_outseq, 
                    state_expected_inseq,
                    state_challenge)
                print("Sending AUTHREQ", resp, state_outseq, state_expected_inseq)
                sock.sendto(resp, addr)
                state_outseq += 1                
                state = State.NEW2

            else:
                print("Invalid token")
                state = State.IDLE
        else:
            print("Ignoring unknown message")

    # In this state we are waiting for an AUTHREP
    elif state == State.NEW2:
        if is_full_frame(frame) and \
            get_full_type(frame) == 6 and \
            get_full_subclass_c_bit(frame) == False and \
            get_full_subclass(frame) == 9:

            # Decode the information elements
            ies = decode_information_elements(frame[12:])

            if get_full_source_call(frame) == state_source_call_id and \
               get_full_dest_call(frame) == state_call_id and \
                17 in ies:

                rsa_challenge_result = base64.b64decode(ies[17])

                # Here is where the actual validation happens:
                try:
                    public_key.verify(rsa_challenge_result,
                        state_challenge.encode("utf-8"), 
                        padding.PKCS1v15(), 
                        hashes.SHA1())
                except:
                    print("Authentication failed")
                    state = State.IDLE
                    continue

                print("Authenticated!")

                # Send ACK
                resp = make_ACK_frame(state_call_id, 
                    state_source_call_id,
                    state_call_start_ms + (current_ms() - state_call_start_stamp),
                    state_outseq, 
                    state_expected_inseq)
                print("Sending ACK", resp, state_outseq, state_expected_inseq)
                sock.sendto(resp, addr)
                # IMPORTANT: We don't move the outseq forward!

                # Send the ACCEPT
                resp = make_ACCEPT_frame(state_call_id, 
                    state_source_call_id,
                    state_call_start_ms + (current_ms() - state_call_start_stamp),
                    state_outseq, 
                    state_expected_inseq)
                print("Sending ACCEPT", resp, state_outseq, state_expected_inseq)
                sock.sendto(resp, addr)
                state_outseq += 1

                # Send the RINGING
                resp = make_RINGING_frame(state_call_id, 
                    state_source_call_id,
                    state_call_start_ms + (current_ms() - state_call_start_stamp),
                    state_outseq, 
                    state_expected_inseq)
                print("Sending RINGING", resp, state_outseq, state_expected_inseq)
                sock.sendto(resp, addr)
                state_outseq += 1

                state = State.RINGING
                state_timeout = current_ms() + 2000

            else:
                print("AUTHREP error")
        else:
            print("Ignoring unknown message NEW2")

    elif state == State.RINGING:

        if is_VOICE_frame(frame):
            # Send ACK
            resp = make_ACK_frame(state_call_id, 
                state_source_call_id,
                state_call_start_ms + (current_ms() - state_call_start_stamp),
                state_outseq, 
                state_expected_inseq)
            print("Sending ACK", resp, state_outseq, state_expected_inseq)
            sock.sendto(resp, addr)
            # IMPORTANT: We don't move the outseq forward!

            g711_audio = frame[12:]
            pcm_audio_48k = upsample(decode_ulaw(g711_audio))
            if audio_device_play.write(make_s16_le(pcm_audio_48k)) < 0:
                print("Playback error")
        
        elif is_mini_voice_packet(frame):
            g711_audio = frame[4:]
            pcm_audio_48k = upsample(decode_ulaw(g711_audio))
            if audio_device_play.write(make_s16_le(pcm_audio_48k)) < 0:
                print("Playback error")
        
        else:
            print("Ignoring unknown message RINGING")

    elif state == State.IN_CALL:

        if is_HANGUP_frame(frame):
            resp = make_ACK_frame(state_call_id, 
                state_source_call_id,
                state_call_start_ms + (current_ms() - state_call_start_stamp),
                state_outseq, 
                state_expected_inseq)
            print("Sending ACK", resp, state_outseq, state_expected_inseq)
            sock.sendto(resp, addr)
            # IMPORTANT: We don't move the outseq forward!

            print("Hangup")
            state = State.IDLE

        elif is_VOICE_frame(frame):
            # Send ACK
            resp = make_ACK_frame(state_call_id, 
                state_source_call_id,
                state_call_start_ms + (current_ms() - state_call_start_stamp),
                state_outseq, 
                state_expected_inseq)
            print("Sending ACK", resp, state_outseq, state_expected_inseq)
            sock.sendto(resp, addr)
            # IMPORTANT: We don't move the outseq forward!

            g711_audio = frame[12:]
            pcm_audio_48k = upsample(decode_ulaw(g711_audio))
            if audio_device_play.write(make_s16_le(pcm_audio_48k)) < 0:
                print("Playback error")

        elif is_mini_voice_packet(frame):
            g711_audio = frame[4:]
            pcm_audio_48k = upsample(decode_ulaw(g711_audio))
            if audio_device_play.write(make_s16_le(pcm_audio_48k)) < 0:
                print("Playback error")

        else:
            print("Ignoring unknown message IN_CALL")
