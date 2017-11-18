#!/usr/bin/env python
#  * *  *   *   *     /usr/bin/flock -n /run/mice.lockfile /usr/bin/python -u /root/avsync/mice.py >> /nas/cronlog 2>&1
import sys
import struct
from subprocess import call
import threading
import time
import Queue
import select
import signal, os
from datetime import datetime

mice_q = Queue.Queue()

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

def get_mice_event(f_mice):
	buf = f_mice.read(3)
	button = ord( buf[0] )
	bLeft = (button & 0x1) > 0
	bMiddle = ( button & 0x4 ) > 0
	bRight = ( button & 0x2 ) > 0
	x,y = struct.unpack( "bb", buf[1:] )
	#print ("L:%d, M: %d, R: %d, x: %d, y: %d\n" % (bLeft, bMiddle, bRight, x, y) )
	return bLeft, bRight

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

def state_machine(left, right) :
	global gState
	state_old = gState
	if gState == 'IDLE' :
		if left and not right :
			gState = 'RECORD'
			cmd_line = arecord_cmd()
			exec_cmd(cmd_line)
		elif left and right :
			if last_wav == '' : # nothing to play
				return
			gState = 'PLAY'
			cmd_line = aplay_cmd()
			exec_cmd(cmd_line)
	elif gState == 'RECORD' :
		if right and not left :
			gState = 'IDLE'
			cmd_line = kill_cmd()
			exec_cmd(cmd_line)
	elif gState == 'PLAY' :
		if left and right :
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
		while not mice_q.empty() :
			left, right = mice_q.get()
			print "LEFT/RIGHT: ", left, right
			state_machine(left, right)
			mice_q.task_done
	print worker + " done!"

def worker_mice():
	worker = sys._getframe().f_code.co_name
	print worker + " starting..."
	f_mice = open( "/dev/input/mice", "rb" )
	left = left_old = False
	right = right_old = False
	timeout = 0.2
	while not gExit:
		rlist, wlist, xlist = select.select([f_mice.fileno()], [], [], timeout)
		if len(rlist) == 0 :
			# timeout, key is stable
			if (left_old != left) or (right_old != right) :
				# generate event only when something changed
				mice_q.put( (left,right) )
				left_old = left
				right_old = right
		else:
			# readable
			left, right = get_mice_event(f_mice)
			
	f_mice.close()
	print worker + " done!"


if __name__ == '__main__':

	signal.signal(signal.SIGTERM, handler)
	signal.signal(signal.SIGINT, handler)
	
	t_ctrl = threading.Thread( target = worker_ctrl )
	t_mice = threading.Thread( target = worker_mice )
	t_mice.start()
	t_ctrl.start()
	
	while not gExit :
		time.sleep(1)
