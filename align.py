#!/usr/bin/env python
import scipy.io.wavfile
import numpy as np
from subprocess import call
import math
import os
import argparse

# Extract audio from video file, save as wav auido file
# INPUT: Video file
def extract_audio(in_file):
	filename, file_ext = os.path.splitext(in_file)
	output = filename + "_MONO.wav"
	cmd_line = ["ffmpeg", "-y", "-i", in_file, "-vn", "-ac", "1", "-f", "wav", output]
	print cmd_line
	call(cmd_line)
	return output


# Read file
# INPUT: Audio file
# OUTPUT: Sets sample rate of wav file, Returns data read from wav file (numpy array of integers)
def read_audio(audio_file):
	rate, data = scipy.io.wavfile.read(audio_file)  # Return the sample rate (in samples/sec) and data from a WAV file
	return data, rate


def make_horiz_bins(data, fft_bin_size, overlap, box_height):
	horiz_bins = {}
	# process first sample and set matrix height
	sample_data = data[0:fft_bin_size]  # get data for first sample
	if (len(sample_data) == fft_bin_size):  # if there are enough audio points left to create a full fft bin
		intensities = fourier(sample_data)  # intensities is list of fft results
		for i in range(len(intensities)):
			box_y = i/box_height
			if horiz_bins.has_key(box_y):
				horiz_bins[box_y].append((intensities[i], 0, i))  # (intensity, x, y)
			else:
				horiz_bins[box_y] = [(intensities[i], 0, i)]
	# process remainder of samples
	x_coord_counter = 1  # starting at second sample, with x index 1
	for j in range(int(fft_bin_size - overlap), len(data), int(fft_bin_size-overlap)):
		sample_data = data[j:j + fft_bin_size]
		if (len(sample_data) == fft_bin_size):
			intensities = fourier(sample_data)
			for k in range(len(intensities)):
				box_y = k/box_height
				if horiz_bins.has_key(box_y):
					horiz_bins[box_y].append((intensities[k], x_coord_counter, k))  # (intensity, x, y)
				else:
					horiz_bins[box_y] = [(intensities[k], x_coord_counter, k)]
		x_coord_counter += 1

	return horiz_bins


# Compute the one-dimensional discrete Fourier Transform
# INPUT: list with length of number of samples per second
# OUTPUT: list of real values len of num samples per second
def fourier(sample):  #, overlap):
	mag = []
	fft_data = np.fft.fft(sample)  # Returns real and complex value pairs
	for i in range(len(fft_data)/2):
		r = fft_data[i].real**2
		j = fft_data[i].imag**2
		mag.append(round(math.sqrt(r+j),2))

	return mag


def make_vert_bins(horiz_bins, box_width):
	boxes = {}
	for key in horiz_bins.keys():
		for i in range(len(horiz_bins[key])):
			box_x = horiz_bins[key][i][1] / box_width
			if boxes.has_key((box_x,key)):
				boxes[(box_x,key)].append((horiz_bins[key][i]))
			else:
				boxes[(box_x,key)] = [(horiz_bins[key][i])]

	return boxes


def find_bin_max(boxes, maxes_per_box):
	freqs_dict = {}
	for key in boxes.keys():
		max_intensities = [(1,2,3)]
		for i in range(len(boxes[key])):
			if boxes[key][i][0] > min(max_intensities)[0]:
				if len(max_intensities) < maxes_per_box:  # add if < number of points per box
					max_intensities.append(boxes[key][i])
				else:  # else add new number and remove min
					max_intensities.append(boxes[key][i])
					max_intensities.remove(min(max_intensities))
		for j in range(len(max_intensities)):
			if freqs_dict.has_key(max_intensities[j][2]):
				freqs_dict[max_intensities[j][2]].append(max_intensities[j][1])
			else:
				freqs_dict[max_intensities[j][2]] = [max_intensities[j][1]]

	return freqs_dict


def find_freq_pairs(freqs_dict_orig, freqs_dict_sample):
	time_pairs = []
	for key in freqs_dict_sample.keys():  # iterate through freqs in sample
		if freqs_dict_orig.has_key(key):  # if same sample occurs in base
			for i in range(len(freqs_dict_sample[key])):  # determine time offset
				for j in range(len(freqs_dict_orig[key])):
					time_pairs.append((freqs_dict_sample[key][i], freqs_dict_orig[key][j]))

	return time_pairs


def find_delay(time_pairs):
	t_diffs = {}
	for i in range(len(time_pairs)):
		delta_t = time_pairs[i][0] - time_pairs[i][1]
		if t_diffs.has_key(delta_t):
			t_diffs[delta_t] += 1
		else:
			t_diffs[delta_t] = 1
	t_diffs_sorted = sorted(t_diffs.items(), key=lambda x: x[1])
	#print t_diffs_sorted
	time_delay = t_diffs_sorted[-1][0]

	return time_delay


# Find time delay between two video files
def align(av_base, av_file, fft_bin_size=1024, overlap=0, box_height=512, box_width=43, samples_per_box=7):
	# Process first file
	wavfile1 = extract_audio(av_base)
	raw_audio1, rate = read_audio(wavfile1)
	bins_dict1 = make_horiz_bins(raw_audio1[:rate*120], fft_bin_size, overlap, box_height) #bins, overlap, box height
	boxes1 = make_vert_bins(bins_dict1, box_width)  # box width
	ft_dict1 = find_bin_max(boxes1, samples_per_box)  # samples per box

	# Process second file
	wavfile2 = extract_audio(av_file)
	raw_audio2, rate = read_audio(wavfile2)
	bins_dict2 = make_horiz_bins(raw_audio2[:rate*60], fft_bin_size, overlap, box_height)
	boxes2 = make_vert_bins(bins_dict2, box_width)
	ft_dict2 = find_bin_max(boxes2, samples_per_box)

	# Determie time delay
	pairs = find_freq_pairs(ft_dict1, ft_dict2)
	delay = find_delay(pairs)
	samples_per_sec = float(rate) / float(fft_bin_size)
	seconds= round(float(delay) / float(samples_per_sec), 4)

	if seconds > 0:
		return (0, seconds)
	else:
		return (abs(seconds), 0 )

# trim av file
def trim_av(in_file, seconds, len=''):
	filename, file_ext = os.path.splitext(in_file)
	out_file = filename + "_TRIMED" + file_ext
	time_s = '%.3f' % (seconds) #22.115
	if len :
		cmd_line = ["ffmpeg", "-t", len, "-y", "-ss", time_s, "-i", in_file, "-vcodec", "libx264", "-crf", "18", "-c:a", "copy", out_file]
	else:
		cmd_line = ["ffmpeg", "-y", "-ss", time_s, "-i", in_file, "-codec", "copy", out_file]
	print cmd_line
	call(cmd_line)
	return out_file

def replace_audio(video_file, wav_file):
	filename, file_ext = os.path.splitext(video_file)
	out_file = filename + "_Av" + file_ext
	cmd_line = ["ffmpeg", "-y", "-i", video_file, "-i", wav_file, "-c:v", "copy", "-c:a", "aac", "-b:a", "256k", 
"-strict", "experimental",
	"-map", "0:v", "-map", "1:a", "-shortest", out_file]
	print cmd_line
	call(cmd_line)

if __name__ == '__main__':
	parser = argparse.ArgumentParser()
	parser.add_argument('audio', help='audio file ./path/audio_name.ext')
	parser.add_argument('video', help='video file ./path/video_name.ext')
	parser.add_argument('-v', help='video file pop sound start second')
	parser.add_argument('-a', help='audio file pop sound start second')
	parser.add_argument('-l', help='final video length in second')
	
	args = parser.parse_args()
	if args.v :
		tv = args.v
		t_file = float(args.v)
	if args.a :
		ta = args.a
		t_base = float(args.a)
	if args.l :
		len = args.l

	av_base = args.audio
	av_file = args.video

	#av_base = "./media/Waltz_r.wav"
	#av_file = "./media/Waltz_v1.mp4"

	if not args.v:
		t_base, t_file = align(av_base, av_file)

	if t_base + t_file < 0.2:
		print "Time difference is less than 0.2 second, no action."
		quit()
	av_base_trimed = av_base;
	av_file_trimed = av_file;
	if (t_base != 0): #audio
		print "------ %s will be trimed from %.3f second ---" % (av_base, t_base)
		av_base_trimed = trim_av(av_base, t_base)
	if (t_file != 0):
		print "------ %s will be trimed from %.3f second ---" % (av_file, t_file)
		av_file_trimed = trim_av(av_file, t_file, len)
	print "------ Audio start @", t_base, ", video start @", t_file
	replace_audio(av_file_trimed, av_base_trimed)

#ffmpeg -y -t 57 -ss 4.634 -i DSC_3554.MOV -ss 9.535 -i DSC_3554_Ryan_1.wav -c:v libx264 -crf 18 -c:a aac -b:a 256k -map 0:v -map 1:a -shortest -strict -2 DSC_3554_Av.MOV

#ffmpeg -y -t 78 -ss 6.841 -i DSC_3557.MOV -ss 31.380 -i DSC_3557_Eleanor_1.wav -c:v libx264 -crf 18 -c:a aac -b:a 256k -map 0:v -map 1:a -shortest -strict -2 DSC_3557_Av.MOV