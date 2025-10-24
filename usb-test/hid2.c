/*
A demonstration of accessing the HID registers of an USB audio device.
Copyright (C) 2025, Bruce MacKinnon, KC1FSZ

Here we just read the HID registers forever. An event should be generated
any time the status of the device changes (i.e. pressing buttons or
toggling GPIOs).
*/
#include <stdio.h>
#include <stdlib.h>
#include <unistd.h>
#include <fcntl.h>

//gcc -Wall hid2.c -o hid2

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

    // Issue a "Set Output Report" HID request to select a specific register.
    char buf[4];
    buf[0] = 48;
    buf[1] = 0;
    buf[2] = 0;
    buf[3] = 3;
    ssize_t bytes_write = write(fd, buf, sizeof(buf));
    printf("Bytes Written %ld\n", bytes_write);

    // Wait for some response
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
