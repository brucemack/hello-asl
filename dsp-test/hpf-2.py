# Analysis of the ASL pre-emphais filter in chan_simpleusb.c
# Copyright (C) 2025, Bruce MacKinnon KC1FSZ
#
import numpy as np
from scipy.signal import firwin, lfilter, lfilter_zi, freqz, cheby1
import matplotlib.pyplot as plt

fs = 8000
fny = fs / 2
rp = 0.5
fc = 100

# From the ASL code
c0 = 17610
c1 = -17610

# Reorganize into FIR form
a0 = 1
a1 = 0
b0 = c0 / 13414
b1 = c1 / 13414
b1 = np.array([ b0, b1 ])
a1 = np.array([ a0, a1 ])

# Response analysis
w1, h1 = freqz(b1, a1)
f1 = w1 * (fs / (2 * 3.14159))
print("b1 (ASL)", b1)
print("a1 (ASL)", a1)

"""
# Theoretical from the model
b2, a2 = cheby1(1, rp, fc / fny, btype='lowpass', analog=False)
w2, h2 = freqz(b2, a2)
f2 = w2 * (fs / (2 * 3.14159))
print("b2 (Model)", b2)
print("a2 (Model)", a2)
"""

# Plot magnitude and phase response
fig, (ax1, ax2) = plt.subplots(2, 1, layout='compressed')
ax1.set_title('Frequency Response')
ax1.set_xscale('log')
ax1.axvline(x=300, color='r', linestyle='--', label='300Hz')
ax1.plot(f1, 20 * np.log10(abs(h1) * 3), label="Coefficents from code")
#ax1.plot(f2, 20 * np.log10(abs(h2)), label="Model")
ax1.set_ylabel('Magnitude (dB)')
ax1.set_xlabel('Frequency (Hz) log')
ax1.legend()
ax1.grid(True)

angles1 = np.unwrap(np.angle(h1))
#angles2 = np.unwrap(np.angle(h2))
ax2.set_xscale('log')
ax2.axvline(x=300, color='r', linestyle='--', label='300Hz')
ax2.plot(f1, angles1)
#ax2.plot(f2, angles2)
ax2.set_ylabel('Phase (radians)')
ax2.set_xlabel('Frequency (Hz) log')
ax2.grid(True)

plt.show()

