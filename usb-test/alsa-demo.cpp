/*
A demonstration of the ALSA API.
This generates a tone on the default audio output device.
*/
// Need to install the libaound2-dev pacakge to get this:
#include <alsa/asoundlib.h>
#include <iostream>
#include <cmath> 

// g++ -Wall alsa-demo.cpp -lasound -o alsa-demo

static const char *device = "default"; // Or "hw:0,0", etc.

using namespace std;

int main() {

    snd_pcm_t *playback_handle;
    int err;

    if ((err = snd_pcm_open(&playback_handle, device, SND_PCM_STREAM_PLAYBACK, 0)) < 0) {
        cerr << "Cannot open audio device " << device << " (" << snd_strerror(err) << ")" << endl;
        return 1;
    }

    snd_pcm_hw_params_t *hw_params;
    snd_pcm_hw_params_alloca(&hw_params);
    snd_pcm_hw_params_any(playback_handle, hw_params);
    snd_pcm_hw_params_set_access(playback_handle, hw_params, SND_PCM_ACCESS_RW_INTERLEAVED);
    snd_pcm_hw_params_set_format(playback_handle, hw_params, SND_PCM_FORMAT_S16_LE);
    unsigned int rate = 44100;
    snd_pcm_hw_params_set_rate_near(playback_handle, hw_params, &rate, 0);
    const unsigned int channels = 2;
    unsigned int channelsTemp = channels;
    snd_pcm_hw_params_set_channels_near(playback_handle, hw_params, &channelsTemp);

    if ((err = snd_pcm_hw_params(playback_handle, hw_params)) < 0) {
        cerr << "Cannot set parameters (" << snd_strerror(err) << ")" << endl;
        snd_pcm_close(playback_handle);
        return 1;
    }

    const int buffer_size = 4096;
    // Stereo, 16-bit samples    
    short buffer[buffer_size * channels];
    // Play for 5 seconds    
    for (unsigned i = 0; i < 5 * rate / buffer_size; ++i) {
        for (int j = 0; j < buffer_size; ++j) {
            // 16-bit with 10,000 as full-scale
            // 440Hz sine wave
            short sample = 10000 * sinf(2 * M_PI * 440 * ((float)(i * buffer_size + j) / rate)); 
            buffer[j * channels] = sample;     // Left channel
            buffer[j * channels + 1] = sample; // Right channel
        }

        // writei() writes interleaved frames 
        if ((err = snd_pcm_writei(playback_handle, buffer, buffer_size)) < 0) {
            cerr << "Write failed (" << snd_strerror(err) << ")" << endl;
            snd_pcm_prepare(playback_handle); // Try to recover
        }
    }

    // Needed to allow the sound to be heard
    sleep(10);

    snd_pcm_close(playback_handle);
    return 0;
}