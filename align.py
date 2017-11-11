#!/usr/bin/env python
import scipy.io.wavfile
import numpy as np
from subprocess import call
import math
import os
import argparse

# Extract audio from video file, convert to fixed sample rate mono
def extract_audio(in_file):
	filename, file_ext = os.path.splitext(in_file)
	output = filename + "_MONO.wav"
	cmd_line = ["ffmpeg", "-y", "-i", in_file, "-vn", "-ac", "1", "-c:a", "pcm_s16le", "-ar", "44100", output]
	print ' '.join(str(e) for e in cmd_line)
	call(cmd_line)
	return output

# build freq chart
#{ band 0: [(i00, 0, 0), (i01, 0, 1), ... (i01, 0, 511), (i10, 1, 0), (i11, 1, 1), ... (i11, 1, 511, ...), ...], band 1: [...], ...}
def make_horiz_bins(data, fft_bin_size, overlap, box_height):
	horiz_bins = {}
	x_coord_counter = 0
	for j in range(0, len(data) - fft_bin_size, int(fft_bin_size - overlap)):
		sample_data = data[j:j + fft_bin_size]
		intensities = fourier(sample_data) # =>list of 512 intensities
		for k in range(len(intensities)):
			box_y = k/box_height # box_y always 0, as box_height = 512
			if horiz_bins.has_key(box_y):
				horiz_bins[box_y].append((intensities[k], x_coord_counter, k))  # (intensity, x, y)
			else:
				horiz_bins[box_y] = [(intensities[k], x_coord_counter, k)]
		x_coord_counter += 1

	return horiz_bins

# Compute the one-dimensional discrete Fourier Transform
# INPUT: list of samples of fft_bin_size
def fourier(sample):  #, overlap):
	fft_data = np.fft.fft(sample)  # Returns real and complex value pairs
	half_len = len(fft_data) / 2
	mag = np.round(abs(fft_data[:half_len]), 2)
	#print "--------->\n", mag[:half_len]
	return mag

# seperate horiz_bins by every second
def make_vert_bins(horiz_bins, box_width):
	boxes = {}
	for key in horiz_bins.keys():
		for i in range(len(horiz_bins[key])):
			# box_width=43, => 43*1024/44.1 = 0.9985 second
			# box_x is time in second
			box_x = horiz_bins[key][i][1] / box_width
			if boxes.has_key((box_x,key)):
				boxes[(box_x,key)].append((horiz_bins[key][i]))
			else:
				boxes[(box_x,key)] = [(horiz_bins[key][i])]

	return boxes

# find maxes_per_box max intensity points in every box, put them into freq_dict
# freqs_dict = { freq 0: [t01, t02...], freq 1:[t11, t12, ...], freq x:[tx1, tx2, ....]
def find_bin_max(boxes, maxes_per_box):
	freqs_dict = {}
	for key in boxes.keys(): # for every second in boxes
		max_intensities = [(1,2,3)] # [(intensity, x, y)]
		for i in range(len(boxes[key])): # for every t in given second
			if boxes[key][i][0] > min(max_intensities)[0]:
				if len(max_intensities) < maxes_per_box:  # add if < number of points per box
					max_intensities.append(boxes[key][i])
				else:  # else add new number and remove min
					max_intensities.append(boxes[key][i])
					max_intensities.remove(min(max_intensities))
		# add intensities of this second (num < maxes_per_box) to freq dict
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

# example
# freq1_orig: Pt1, Pt2
# freq1_orig: 6,   7
# freq1_samp: Qtx, Qt1, Qt2, Qty
# freq1_samp: 11,  16,  17,  20
# time_pairs: (Pt1, Qtx), (Pt1, Qt1), (Pt1, Qt2), (Pt1, Qty), (Pt2, Qtx), (Pt2, Qt1), (Pt2, Qt2), (Pt2, Qty)
# delta_t:    Pt1-Qtx,    -T,         -T - rate,  Pt1-Qty,    Pt2-Qtx,    -T + rate,   -T         Pt2-Qty
# delta_t:    -5,         -10,        -11,        -14,        -4,         -9,         -10         -13
# t_diffs:    {[-5: 1], [-10: 2], [-11: 1], [-14: 1], ...}
# found max count is '2', delay is '-10', max should be the count of overlaped intensities
def find_delay(time_pairs):
	t_diffs = {}
	for i in range(len(time_pairs)):
		delta_t = time_pairs[i][0] - time_pairs[i][1]
		if t_diffs.has_key(delta_t):
			t_diffs[delta_t] += 1
		else:
			t_diffs[delta_t] = 1
	t_diffs_sorted = sorted(t_diffs.items(), key=lambda x: x[1])

	for t in t_diffs_sorted[-10:]:
		print "Time diff = %4d K samples, hit %3d times" % (t[0], t[1])

	time_delay = t_diffs_sorted[-1][0]

	return time_delay

# Find time delay between two files
def align(av_base, av_file, fft_bin_size=1024, overlap=0, box_height=512, box_width=43, samples_per_box=7, match_len=120):
	# Process first file
	wavfile1 = extract_audio(av_base)
	rate, raw_audio1 = scipy.io.wavfile.read(wavfile1)
	bins_dict1 = make_horiz_bins(raw_audio1[:rate*match_len], fft_bin_size, overlap, box_height) #bins, overlap, box height
	boxes1 = make_vert_bins(bins_dict1, box_width)  # box width
	ft_dict1 = find_bin_max(boxes1, samples_per_box)  # samples per box
	#print "=======================ft_dict1============================="
	#print ft_dict1

	# Process second file
	wavfile2 = extract_audio(av_file)
	rate, raw_audio2 = scipy.io.wavfile.read(wavfile2)
	bins_dict2 = make_horiz_bins(raw_audio2[:rate*match_len], fft_bin_size, overlap, box_height)
	boxes2 = make_vert_bins(bins_dict2, box_width)
	ft_dict2 = find_bin_max(boxes2, samples_per_box)
	#print "=======================ft_dict2============================="
	#print ft_dict2

	# Determie time delay
	print "======================= Determie time delay ============================="
	pairs = find_freq_pairs(ft_dict1, ft_dict2)
	#print pairs
	delay = find_delay(pairs)
	samples_per_sec = float(rate) / float(fft_bin_size)
	seconds= round(float(delay) / float(samples_per_sec), 4)

	if seconds > 0:
		return (0, seconds)
	else:
		return (abs(seconds), 0 )


cmd_line = ["ffmpeg"]
if __name__ == '__main__':
	parser = argparse.ArgumentParser()
	parser.add_argument('audio', help='audio file ./path/audio_name.ext')
	parser.add_argument('video', help='video file ./path/video_name.ext')
	parser.add_argument('-a_delay', help='adjust audio output delay in second. (0.041)')
	parser.add_argument('-s', help='offset of video start in second')
	parser.add_argument('-t', help='final video duration in second')
	parser.add_argument('-m', help='iOS compatible with iPhone4/iPad/Apple TV 2', action="store_true")

	offset = "0.0"
	args = parser.parse_args()
	if args.s :
		offset = args.s

	if args.t :
		out_len = args.t
		cmd_line += ["-t", out_len]

	av_audio = args.audio
	av_video = args.video

	a_start, v_start = align(av_audio, av_video)
	a_start += float(offset);
	v_start += float(offset);
	
	if args.a_delay :
		a_start -= float(args.a_delay)

	filename, file_ext = os.path.splitext(av_audio)
	if args.m :
		filename += ".m"
	output = filename + ".mp4"

	cmd_line += ["-ss", str(a_start), "-i", av_audio, "-ss", str(v_start), "-i", av_video]
	cmd_line +=	["-c:v", "libx264", "-crf", "18"]
	if args.m :
		cmd_line += ["-profile:v", "main", "-level", "3.1", "-vf", "scale=iw/2:-1"]
	cmd_line += ["-c:a", "aac", "-b:a", "256k", "-strict", "-2"]
	cmd_line += ["-map", "0:a", "-map", "1:v", "-y", output]

	print ' '.join(str(e) for e in cmd_line)
	call(cmd_line)

	# ./align.py "./media/DSC_3554_Ryan_1.wav" "./media/DSC_3554.MOV"
	# ./align.py ./media/DSC_3555_Ryan_2.wav ./media/DSC_3555.MOV
