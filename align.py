#!/usr/bin/env python
import scipy.io.wavfile
import numpy as np
from subprocess import call
import math
import re
import os, glob
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
	print "================================ Determie time offset ================================="

	pairs = find_freq_pairs(ft_dict1, ft_dict2)
	#print pairs
	delay = find_delay(pairs)
	samples_per_sec = float(rate) / float(fft_bin_size)
	seconds= round(float(delay) / float(samples_per_sec), 4)

	print "====================== Audio is ahead of video %8.4f seconds =======================" % -(seconds)
	# remove temp files
	tmp_files = glob.glob("*_MONO.wav")
	for tmp_file in tmp_files:
		print "removing", tmp_file, "..."
		os.remove(tmp_file)

	return -(seconds)

def key_frame_time(v_file):
	key_list = []
	key_file = v_file + ".key"
	if not os.path.isfile(key_file):
		print "Analyzing %s for key frames ..." % v_file
		cmd_line = ["ffprobe", "-v", "error", "-skip_frame", "nokey", "-select_streams", "v:0", 
		"-show_entries", "frame=pkt_pts_time", "-of", "csv=print_section=0", v_file]
		print ' '.join(str(e) for e in cmd_line)
		with open(key_file, 'w') as f:
			call(cmd_line, stdout=f)
	
	if os.path.isfile(key_file):
		print "Load key frame positions from file %s" % key_file
		key_list = np.loadtxt(key_file)

	print "Found %d key frames in video %s" % (len(key_list), v_file)
	return key_list

# convert to seconds, "00:22.6"->22.6, "00:01:22.6"->82.6, "01:01:22.6"->3682.6, "22.6"->22.6
def time_to_second(time_str):
	times = map(float, time_str.split(":"))
	if len(times) == 3:
		t = times[0] * 3600 + times[1] * 60 + times[2]
	elif len(times) == 2:
		t = times[0] * 60 + times[1]
	elif len(times) == 1:
		t = times[0]
	else:
		t = 0.0
	return t

def nearest_key_frame(key_list, t):
	p = 0
	while p+1 < len(key_list) and t > key_list[p+1] :
		p += 1
	return key_list[p]
'''
def nearest_key_frame(key_list, t):
	p = 0
	while p < len(key_list) and key_list[p] < t :
		p += 1
	return key_list[p]
'''	
def clip_encode(a_start, v_start, v_end, audio, video, output, re_encode=False, mobile_version=False, extra=""):
	# extract video
	# ffmpeg -ss 663.245417 -i DSC_5661.MOV -t 229.254583 -c:v copy -an -avoid_negative_ts make_zero -y temp_video.mov
	cmd_line = ["ffmpeg"]
	cmd_line += ["-ss", str(v_start), "-i", video, "-t", str(v_end - v_start)]

	if re_encode:
		cmd_line +=	["-c:v", "libx264", "-crf", "18"]
		# GOP default 250 -> 120 (multiple of 24, 30, 60)
		cmd_line += ["-tune", "film", "-g", "120"]
		if mobile_version :
			cmd_line += ["-profile:v", "main", "-level", "3.1", "-vf", "scale=iw/2:-2"]
	else:
		cmd_line +=	["-c:v", "copy"]

	cmd_line += ['-an', '-avoid_negative_ts', 'make_zero']
	cmd_line += ["-y", "temp_video.mov"]

	print ' '.join(str(e) for e in cmd_line)
	call(cmd_line)

	# extract audio
	# ffmpeg -ss 666.344517 -i 190407_DSC_5661V.wav -t 229.254583 -c: copy -y temp_audio.wav
	cmd_line = ["ffmpeg"]
	cmd_line += ["-ss", str(a_start), "-i", audio, "-t", str(v_end - v_start)]

	#cmd_line += ["-c:a", "aac", "-b:a", "256k", "-strict", "-2"]
	cmd_line += ["-c:a", "copy"]
	cmd_line += ["-y", "temp_audio.wav"]

	print ' '.join(str(e) for e in cmd_line)
	call(cmd_line)

	# mux audio and video
	# ffmpeg -i audio_only.wav -i video_only.mov -c:a copy -c:v copy -map 1:v -map 0:a -y -shortest audio_video.mov
	cmd_line = ["ffmpeg"]
	cmd_line += ["-i", "temp_audio.wav", "-i", "temp_video.mov", "-c", "copy", "-map", "1:v", "-map", "0:a", "-shortest"]
	
	if extra != "":
		extra_opts = extra.split()
		cmd_line += extra_opts

	cmd_line += ["-y", output]

	print ' '.join(str(e) for e in cmd_line)
	call(cmd_line)

if __name__ == '__main__':
	parser = argparse.ArgumentParser()
	parser.add_argument('audio', help='audio file ./path/audio_name.ext')
	parser.add_argument('video', help='video file ./path/video_name.ext')
	parser.add_argument('-a_delay', help='adjust audio output delay. (default=0.0417 24fps)', dest='a_delay', default=0.0417)
	parser.add_argument('-r', help='re-encode video using libx264')
	parser.add_argument('-c', '--clip', action='append', help='video clips in format: 00:00.000-59:59.999')
	parser.add_argument('-m', help='iOS compatible with iPhone4/iPad/Apple TV 2', action="store_true")
	parser.add_argument('-e', help='extra options', default="")

	args = parser.parse_args()

	re_encode = False

	av_audio = args.audio
	av_video = args.video

	key_list = key_frame_time(av_video)

	a_delay = align(av_audio, av_video)
	a_delay -= 0.5005 # FIXME !!!

	if a_delay < 0 :
		print "============================= Audio should cover video ! =============================="
		quit()
	if args.m or args.r:
		print "============================= Video will be re-encoded ! =============================="
		re_encode = True

	a_name, a_ext = os.path.splitext(av_audio)
	v_name, v_ext = os.path.splitext(av_video)
	for clip in args.clip:
		clip_start, clip_end = clip.split('-')
		t_clip_start = time_to_second(clip_start)
		v_start = nearest_key_frame(key_list, t_clip_start)
		t_clip_end = time_to_second(clip_end)
		#print "---------------------> t_clip_start = %f, v_start = %f, t_clip_end= %f" % (t_clip_start, v_start, t_clip_end)
		output = a_name + "_" + v_name + "_%06.1f-%06.1f" % (v_start, t_clip_end)
		if args.m :
			output += ".m"

		output += ".mov"
		
		clip_encode(a_delay+v_start, v_start, t_clip_end, av_audio, av_video, output, re_encode, True if args.m else False, args.e)

	# remove temp files
	tmp_files = glob.glob("temp*.*")
	for tmp_file in tmp_files:
		print "removing", tmp_file, "..."
		os.remove(tmp_file)