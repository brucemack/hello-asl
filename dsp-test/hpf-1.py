# Analysis of hpass6() in chan_simpleusb.c
# Copyright (C) 2025, Bruce MacKinnon KC1FSZ
#
import numpy as np
from scipy.signal import firwin, lfilter, lfilter_zi, freqz, cheby1
import matplotlib.pyplot as plt

fs = 8000
fny = fs / 2
fc = 300
rp = 0.5
g = 1.745882764

# From the ASL code
b1 = [ 1 / g, -6 / g, 15 / g, -20 / g, 15 / g, -6 / g, 1 / g ]
a1 = np.array([1, -4.8664511065, 9.9896695552, -11.0685981760, 6.9905126572, -2.3932556573, 0.3491861578 ])
w1, h1 = freqz(b1, a1)
f1 = w1 * (fs / (2 * 3.14159))
print("b1 (ASL)", b1)
print("a1 (ASL)", a1)

# Theoretical from the model
b2, a2 = cheby1(6, rp, fc / fny, btype='highpass', analog=False)
w2, h2 = freqz(b2, a2)
f2 = w2 * (fs / (2 * 3.14159))
print("b2 (Model)", b2)
print("a2 (Model)", a2)

# Plot magnitude and phase response
fig, (ax1, ax2) = plt.subplots(2, 1, layout='compressed')
ax1.set_title('hpass6() Frequency Response (fc=' + str(fc) + ')')
ax1.set_xscale('log')
ax1.axvline(x=fc, color='r', linestyle='--', label='fc=300')
ax1.plot(f1, 20 * np.log10(abs(h1)), label="Coefficents from ASL code")
ax1.plot(f2, 20 * np.log10(abs(h2)), label="fc=300, rp=0.5")
ax1.set_ylabel('Magnitude (dB)')
ax1.set_xlabel('Frequency (Hz) log')
ax1.legend()
ax1.grid(True)

angles1 = np.unwrap(np.angle(h1))
angles2 = np.unwrap(np.angle(h2))
ax2.set_xscale('log')
ax2.axvline(x=fc, color='r', linestyle='--', label='fc=300')
ax2.plot(f1, angles1)
ax2.plot(f2, angles2)
ax2.set_ylabel('Phase (radians)')
ax2.set_xlabel('Frequency (Hz) log')
ax2.grid(True)

plt.show()


