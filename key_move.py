#!/usr/bin/env python
import scipy.io.wavfile
import numpy as np
from subprocess import call
import math
import os
import argparse
import time
import sys

DELTA = 20 # +/- 20Hz

keys = [0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00,  0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00,  0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00]
notes = [440]
base_freq = 440

color0 = "\033[1;30m"
color1 = "\033[0m"
color2 = "\033[1;37m"
color3 = "\033[1;33m"
color_reset = "\033[0m"
colors = [color0, color1, color2, color3]

def test1 () :
	for t in range (len(keys)) :
		p = 0
		line = ''
		for k in keys[t] :
				s = '%2d'%(k)
				line += s.rjust(k * 2 - p)
				p = k * 2
		t = 0
		while( t - 0.2 < 0.00001) :
			print line
			time.sleep(0.04)
			t += 0.04

def test_keys_init() :
	for t in np.arange (0, np.pi, np.pi/100.) :
		#print np.sin(t)
		for n in [5, 10, 15] :
			keys[n] = int (np.sin(t) * 255)
			#print keys

def test_color() :
	sys.stdout.write(color0)
	print "color0"
	sys.stdout.write(color1)
	print "color1"
	sys.stdout.write(color2)
	print "color2"
	sys.stdout.write(color3)
	print "color3"
	sys.stdout.write(color_reset)
	print "color_reset"

# Extract audio from video file, convert to fixed sample rate mono
def extract_audio(in_file):
	filename, file_ext = os.path.splitext(in_file)
	output = filename + "_MONO.wav"
	cmd_line = ["C:/ffmpeg/bin/ffmpeg", "-y", "-i", in_file, "-vn", "-ac", "1", "-c:a", "pcm_s16le", "-ar", "44100", output]
	print ' '.join(str(e) for e in cmd_line)
	call(cmd_line)
	return output

# Compute the one-dimensional discrete Fourier Transform
# INPUT: list of samples of fft_bin_size
def fourier(sample):  #, overlap):
	fft_data = np.fft.fft(sample)  # Returns real and complex value pairs
	half_len = len(fft_data) / 2
	mag = np.round(abs(fft_data[:half_len]), 2)
	#print "--------->\n", mag[:half_len]
	return mag
	
def get_keys() :
	return

from scipy import signal
import matplotlib.pyplot as plt
def plt_spect(x, fs) :
	f, t, Sxx = signal.spectrogram(x, fs, nfft=1024, noverlap=5, mode='magnitude')
	plt.pcolormesh(t, f, Sxx)
	plt.ylabel('Frequency [Hz]')
	plt.xlabel('Time [sec]')
	plt.show()

import pylab
def plt_spect2(x, fs) :
	Sxx, f, t,  im = pylab.specgram(x, NFFT=1024, Fs=fs, noverlap=5, mode='magnitude')
	plt.pcolormesh(t, f, Sxx)
	plt.ylabel('Frequency [Hz]')
	plt.xlabel('Time [sec]')
	plt.show()
	
if __name__ == '__main__':
	parser = argparse.ArgumentParser()
	parser.add_argument('audio', help='audio file ./path/audio_name.ext')
	parser.add_argument('-m', help='no color for key force', action="store_true")

	args = parser.parse_args()
	av_audio = args.audio

	wavfile = extract_audio(av_audio)
	rate, data = scipy.io.wavfile.read(wavfile)

	plt_spect(data, 44100)
	quit()
	
	fft_bin_size = 1024
	for s in range(0, len(data) - fft_bin_size, fft_bin_size):
		sample_data = data[s:s + fft_bin_size]
		intensities = fourier(sample_data) # =>list of 512 intensities
		for k in range(len(intensities)):
			box_y = k/box_height # box_y always 0, as box_height = 512

	

	
		line = ''
		for k in keys :
			if k == 0 :
				line += '  '
			else :
				line += colors[ k / (256/len(colors)) ]
				line += '%02X' % (k)
		print line

	sys.stdout.write(color_reset)


