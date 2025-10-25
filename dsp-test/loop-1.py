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
# Name of audio device used for output
audio_device_name = "default"
# ===========================================================================

def encode_ulaw(pcm_data):
    # TODO: REMOVE DEPENDENCY ON THIS DEPRECATED LIBRARY
    return audioop.lin2ulaw(pcm_data, 2)

def decode_ulaw(g711_data: bytes):
    # TODO: REMOVE DEPENDENCY ON THIS DEPRECATED LIBRARY
    # Testing has shown that this created little-endian integers
    b = audioop.ulaw2lin(g711_data, 2)
    return struct.unpack(f'<{160}h', b)

"""
# TEST
a = bytearray()
a.append(0b10000000)
r = audioop.ulaw2lin(a, 2)
# Show that the result is in little endian format
print((r[1] << 8 | r[0]) >> 2)
quit()
"""

# Audio output setup
audio_device_play = alsaaudio.PCM(channels=1, rate=48000, format=alsaaudio.PCM_FORMAT_S16_LE, 
                            periodsize=160*6, device=audio_device_name)

audio_device_capture = alsaaudio.PCM(alsaaudio.PCM_CAPTURE, alsaaudio.PCM_NONBLOCK,
                                     channels=1, rate=48000, format=alsaaudio.PCM_FORMAT_S16_LE, 
                            periodsize=160*6, device=audio_device_name)

# FIR filter used for up-sampling setup
sample_rate = 48000
nyq_rate = sample_rate / 2.0
# The cutoff frequency of the filter.
lpf_cutoff_hz = 4300
lpf_N = 31
lpf_beta = 3.0
# Use firwin with a Kaiser window to create a lowpass FIR filter.
lpf_taps = firwin(lpf_N, lpf_cutoff_hz / nyq_rate, window=('kaiser', lpf_beta))
# The zi object is used to maintain the state inside of the
# FIR since we are applying data one block at a time.
lpf_zi = lfilter_zi(lpf_taps, [1])

def upsample(pcm_data_8k):
    global lpf_zi
    pcm_data_48k = []
    # First do the 1:6 expansion
    for s in pcm_data_8k:
        for i in range(0,6):
            pcm_data_48k.append(s)
    # Apply the LPF to the expanded data to prevent aliasing
    # NOTE: zi is being passed around each time to maintain state
    pcm_data_48k, lpf_zi = lfilter(lpf_taps, [1.0], pcm_data_48k, zi=lpf_zi)
    return pcm_data_48k

def make_s16_le(data):
    result = bytearray()
    for d in data:
        i = int(d) 
        low = i & 0xff
        high = (i >> 8) & 0xff
        result.append(low)
        result.append(high)
    return result

def current_ms_frac():
    return time.time() * 1000

while True:
    # Make progress on streaming out audio
    audio_in_l, audio_in_data = audio_device_capture.read()
    if audio_in_l > 0:
        if audio_device_play.write(audio_in_data) < 0:
            print("Playback error")
