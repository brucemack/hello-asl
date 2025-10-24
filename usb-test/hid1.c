/*
A demonstration of accessing the HID registers of an USB audio device.
Copyright (C) 2025, Bruce MacKinnon, KC1FSZ

This is relevant because GPIOs are mapped into the HID register place
on CM1xx style devices.

There are no special APIs being used. We open the raw HID device
and read/write it directly.

Here we just read the HID registers forever. An event should be generated
any time the status of the device changes (i.e. pressing buttons or
toggling GPIOs).
*/
#include <stdio.h>
#include <stdlib.h>
#include <unistd.h>
#include <fcntl.h>

//gcc -Wall hid1.c -o hid1
// Runs as root.

// This will be determined by looking at the installed cards.
// Check out /proc/asound
static const char* usb_dev = "/dev/hidraw0";

int main(int argc, char *argv[])
{
    int fd = open(usb_dev, O_RDWR);
    if (fd < 0) {
        printf("Failed to open\n");
        return -1;
    }

    while (1) {
        unsigned char buffer[64];
        ssize_t bytes_read = read(fd, buffer, sizeof(buffer));
        if (bytes_read < 0) {
            printf("Failed to read from /dev/hidraw0\n");
        } else {
            printf("Good read\n");
            for (unsigned i = 0; i < bytes_read; i++) {
                printf("%d %02X\n", i, (unsigned int)buffer[i]);
            }
        }
    }

    close(fd);
}