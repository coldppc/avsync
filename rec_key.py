#!/usr/bin/env python
#  * *  *   *   *     /usr/bin/flock -n /run/mice.lockfile /usr/bin/python -u /home/sxfan/avsync/rec_key.py >> /nas/cronlog 2>&1
import sys
import struct
from subprocess import call
import threading
import time
import Queue
import select
import signal, os
from datetime import datetime
import evdev

key_q = Queue.Queue()

alsa_pid = '/run/alsa.pid '
SUDO = '' # needed in PC
DIR = '/nas/'

global gExit
gExit = False

global gState
gState = 'IDLE' # idle,  play, record

global last_wav
last_wav = ''

def handler(signum, frame):
	global gExit
	print 'Signal handler called with signal', signum
	with open('/sys/class/leds/led0/trigger', 'w') as text:
		text.write('mmc0')
	gExit = True

def aplay_cmd():
	cmd = SUDO + ' aplay -v -D hw:CARD=USB,DEV=0 -i --process-id-file ' + alsa_pid
	cmd += last_wav
	return cmd

def arecord_cmd() :
	global last_wav
	dt = datetime.now()
	cmd = SUDO + ' arecord -v -f S32_LE -c 2 -r 48000 -D hw:CARD=USB,DEV=0 --process-id-file ' + alsa_pid
	last_wav = DIR + dt.strftime("%Y%m%d_%H%M%S.wav")
	cmd += last_wav
	return cmd

def kill_cmd():
	cmd = SUDO + ' pkill -9 -F ' + alsa_pid
	return cmd

def worker_cmd(cmd):
	words = cmd.split()
	print ' '.join(str(e) for e in words)
	call (words)

def exec_cmd(cmd):
	print "Exec command line in background ..."
	t_cmd = threading.Thread( target = worker_cmd, args = (cmd,))
	t_cmd.start()

def switch_led_state():
	if gState == 'IDLE' :
	        with open('/sys/class/leds/led0/trigger', 'w') as text:
        	        text.write('default-on')
	elif gState == 'RECORD' :
	        with open('/sys/class/leds/led0/trigger', 'w') as text:
        	        text.write('heartbeat')
	elif gState == 'PLAY' :
	        with open('/sys/class/leds/led0/trigger', 'w') as text:
        	        text.write('none')
def state_machine(keys) :
	global gState

	if len(keys) == 0:
		return

	state_old = gState
	if gState == 'IDLE' :
		if keys[0] == evdev.ecodes.KEY_KPASTERISK:
			gState = 'RECORD'
			cmd_line = arecord_cmd()
			exec_cmd(cmd_line)
		elif keys[0] == evdev.ecodes.KEY_KPSLASH :
			if last_wav == '' : # nothing to play
				return
			gState = 'PLAY'
			cmd_line = aplay_cmd()
			exec_cmd(cmd_line)
	elif gState == 'RECORD' :
		if keys[0] ==  evdev.ecodes.KEY_KPASTERISK:
			gState = 'IDLE'
			cmd_line = kill_cmd()
			exec_cmd(cmd_line)
	elif gState == 'PLAY' :
		if keys[0] == evdev.ecodes.KEY_KPSLASH :
			gState = 'IDLE'
			cmd_line = kill_cmd()
			exec_cmd(cmd_line)
	else :
		return
	if gState != state_old :
		switch_led_state()
		print gState

def worker_ctrl():
	worker = sys._getframe().f_code.co_name
	print worker + " starting..."
	switch_led_state()
	while not gExit:
		while not key_q.empty() :
			keys = key_q.get()
			state_machine(keys)
			key_q.task_done
		time.sleep(0.05)
	print worker + " done!"

def worker_key():
        worker = sys._getframe().f_code.co_name
        print worker + " starting..."

	dev = evdev.InputDevice('/dev/input/event0')
	print dev

        timeout = 0.05
        while not gExit:
                rlist, wlist, xlist = select.select([dev], [], [], timeout)
                if len(rlist) == 0 : # timeout
			continue
		for event in dev.read():
			if event.type == evdev.ecodes.EV_KEY:
				print (evdev.categorize(event))
#key event at 1512371912.657925, 98 (KEY_KPSLASH), up
#key event at 1512371913.425918, 55 (KEY_KPASTERISK), down
				if event.value == 1 : # down
					key_q.put([event.code])
        print worker + " done!"


if __name__ == '__main__':

	signal.signal(signal.SIGTERM, handler)
	signal.signal(signal.SIGINT, handler)

	t_ctrl = threading.Thread( target = worker_ctrl )
	t_mice = threading.Thread( target = worker_key )
	t_mice.start()
	t_ctrl.start()

	while not gExit :
		time.sleep(1)
