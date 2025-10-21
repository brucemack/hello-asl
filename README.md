Overview
========

This is a demonstration of a minimal AllStarLink (ASL) hub implemented 
without dependency on the Asterisk system. The purpose of this project
is to study, understand, and document the mechanics of the ASL protocols.
I would not expect anyone to use this program for "production" purposes.

At the moment the server accepts a call, authenticates it, and plays an 
audio announcement. There is no other functionality. Hopefully you 
can see that all of the fundamental mechanisms are in place.

The program is a single Python file. The core essence of ASL is pretty simple.

At the moment you can only connect to the node via the AllStarLink Telephone
Portal. This limitation will be removed shortly once I understand the 
authentication mechanism a bit better.

The AllStarLink user documentation is very good but the technical specifications
are limited. I am working on [protocol documentation here](https://github.com/brucemack/microlink/blob/main/docs/asl_supplement.md).

Steps to Run
============

* Go to https://www.allstarlink.org
* Sign up for AllStarLink and make a contribution to support the system.
* Find your PIN on the Account Settings page.
* Create an AllStarLink server.
* Create a node and assign a password. Make sure that Telephone Portal Access is enabled.
* Clone this GIT repo.
* cd hello-asl
* Customize the top of asl-hub-server.py using your node ID and password.
* Create a Python virtual environment called dev: 
        python3 -m vdev dev
* Activate the virtual environment:
        . dev/bin/activate
* Install dependency packages:
        pip install -r requirements.txt
* Start the server:
        python asl-hub-server.py
* Dial the AllStarLink telephone portal +1 763-230-0000.
* Enter your node ID
* Select option "1"
* Enter your PIN 
* Select option "1"
* You should hear the audio announcement

Work In Process
===============

* Other authentication mechanisms.
* Ability to accept a connection from another node.
* A microcontroller implementation.

References
==========

* IAX2 RFC: https://datatracker.ietf.org/doc/html/rfc5456
* https://github.com/brucemack/microlink/blob/main/docs/asl_supplement.md
# hello-asl
