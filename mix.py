#!/usr/bin/env python
import scipy.io.wavfile
import numpy as np
from subprocess import call
import math
import os
import argparse

cmd_line = ["ffmpeg"]

if __name__ == '__main__':
	parser = argparse.ArgumentParser()
	parser.add_argument('audio', help='audio file ./path/audio_name.ext')
	parser.add_argument('video', help='video file ./path/video_name.ext')
	parser.add_argument('-a', help='pop sound start second in audio file ')
	parser.add_argument('-v', help='pop sound start second in video file ')
	parser.add_argument('-t', help='final video duration in second')
	parser.add_argument('-m', help='iOS compatible with iPhone4/iPad/Apple TV 2', action="store_true")

	args = parser.parse_args()
	if args.v :
		v_start = args.v
	if args.a :
		a_start = args.a
	if args.t :
		out_len = args.t
		cmd_line += ["-t", out_len]

	av_audio = args.audio
	av_video = args.video

	if not args.a and not arg.v:
		a_start, v_start = align(av_audio, av_video)

	filename, file_ext = os.path.splitext(av_audio)
	if args.m :
		filename += ".m"
	output = filename + ".mp4"

	cmd_line += ["-ss", a_start, "-i", av_audio, "-ss", v_start, "-i", av_video]
	cmd_line +=	["-c:v", "libx264", "-crf", "18"]
	if args.m :
		cmd_line += ["-profile:v", "main", "-level", "3.1", "-vf", "scale=iw/2:-1"]
	cmd_line += ["-c:a", "aac", "-b:a", "256k", "-strict", "-2"]
	cmd_line += ["-map", "0:a", "-map", "1:v", "-y", output]

	print ' '.join(str(e) for e in cmd_line)
	call(cmd_line)
# ./mix.py "./media/DSC_3554_Ryan_1.wav" "./media/DSC_3554.MOV" -a 9.535 -v 4.634 -t 57 -m
# ffmpeg -t 57 -ss 9.535 -i ./media/DSC_3554_Ryan_1.wav -ss 4.634 -i ./media/DSC_3554.MOV -c:v libx264 -crf 18 -profile:v main -level 3.1 -vf scale=iw/2:-1 -c:a aac -b:a 256k -strict -2 -map 0:a -map 1:v -y ./media/DSC_3554_Ryan_1.mp4
