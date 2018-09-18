'''
Author: 
	Charles
Function:
	Some utils.
'''
import os
import sys
import math
import time
import torch
import random
import numpy as np
from PIL import Image


'''
Function:
	.cfg file parse and print.
CfgParser().parser():
	Input:
		-cfgfile: .cfg file path.
		-is_print: whether print parse result or not.
	Return:
		-blocks: parse result.
'''
# ----------------------------------------------------------------------------------------------------------------------------------
class CfgParser():
	def __init__(self):
		self.blocks = []
	# Parser .cfg file
	def parser(self, cfgfile, is_print=False):
		fp = open(cfgfile, 'r')
		block = None
		line = fp.readline()
		while line != '':
			line = line.rstrip()
			if line == '' or line[0] == '#':
				line = fp.readline()
				continue
			elif line[0] == '[':
				if block:
					self.blocks.append(block)
				block = dict()
				block['layer_type'] = line.lstrip('[').rstrip(']')
				if block['layer_type'] == 'convolutional':
					block['batch_normalize'] = 0
			else:
				key, value = line.split('=')
				key, value = key.strip(), value.strip()
				block[key] = value
			line = fp.readline()
		if block:
			self.blocks.append(block)
		fp.close()
		if is_print:
			self.__print_parser_result()
		return self.blocks
	# Print function
	def __print_parser_result(self):
		print('layer     filters    size              input                output')
		out_filters, out_widths, out_heights = [], [], []
		# [net] is not a layer.
		ind = -2
		for block in self.blocks:
			ind += 1
			if block['layer_type'] == 'net':
				prev_filters = int(block['channels'])
				prev_width = int(block['width'])
				prev_height = int(block['height'])
				continue
			elif block['layer_type'] in ['convolutional', 'local']:
				filters = int(block['filters'])
				kernel_size = int(block['size'])
				stride = int(block['stride'])
				is_pad = int(block['pad'])
				pad = (kernel_size-1)//2 if is_pad else 0
				width = (prev_width + 2 * pad - kernel_size) // stride + 1
				height = (prev_height + 2 * pad - kernel_size) // stride + 1
				print('%5d %-6s %4d  %d x %d / %d   %3d x %3d x%4d   ->   %3d x %3d x%4d' % (ind, 'conv', filters, kernel_size, kernel_size, stride, prev_width, prev_height, prev_filters, width, height, filters))
				prev_width, prev_height, prev_filters = width, height, filters
				out_filters.append(prev_filters)
				out_heights.append(prev_height)
				out_widths.append(prev_width)
			elif block['layer_type'] == 'maxpool':
				pool_size = int(block['size'])
				stride = int(block['stride'])
				width = prev_width // stride
				height = prev_height // stride
				print('%5d %-6s       %d x %d / %d   %3d x %3d x%4d   ->   %3d x %3d x%4d' % (ind, 'max', pool_size, pool_size, stride, prev_width, prev_height, prev_filters, width, height, filters))
				prev_width, prev_height, prev_filters = width, height, filters
				out_filters.append(prev_filters)
				out_heights.append(prev_height)
				out_widths.append(prev_width)
			elif block['layer_type'] == 'avgpool':
				width, height = 1, 1
				print('%5d %-6s                   %3d x %3d x%4d   ->  %3d' % (ind, 'avg', prev_width, prev_height, prev_filters,  prev_filters))
				prev_width, prev_height, prev_filters = width, height, filters
				out_filters.append(prev_filters)
				out_heights.append(prev_height)
				out_widths.append(prev_width)
			elif block['layer_type'] == 'softmax':
				print('%5d %-6s                                    ->  %3d' % (ind, 'softmax', prev_filters))
				out_filters.append(prev_filters)
				out_heights.append(prev_height)
				out_widths.append(prev_width)
			elif block['layer_type'] == 'cost':
				print('%5d %-6s                                     ->  %3d' % (ind, 'cost', prev_filters))
				out_filters.append(prev_filters)
				out_heights.append(prev_height)
				out_widths.append(prev_width)
			elif block['layer_type'] == 'reorg':
				stride = int(block['stride'])
				filters = stride * stride * prev_filters
				width = prev_width // stride
				height = prev_height // stride
				print('%5d %-6s             / %d   %3d x %3d x%4d   ->   %3d x %3d x%4d' % (ind, 'reorg', stride, prev_width, prev_height, prev_filters, width, height, filters))
				prev_width, prev_height, prev_filters = width, height, filters
				out_filters.append(prev_filters)
				out_heights.append(prev_height)
				out_widths.append(prev_width)
			elif block['layer_type'] == 'upsample':
				stride = int(block['stride'])
				filters = prev_filters
				width = prev_width * stride
				height = prev_height * stride
				print('%5d %-6s           * %d   %3d x %3d x%4d   ->   %3d x %3d x%4d' % (ind, 'upsample', stride, prev_width, prev_height, prev_filters, width, height, filters))
				prev_width, prev_height, prev_filters = width, height, filters
				out_filters.append(prev_filters)
				out_heights.append(prev_height)
				out_widths.append(prev_width)
			elif block['layer_type'] == 'route':
				layers = block['layers'].split(',')
				layers = [int(i) if int(i) > 0 else int(i)+ind for i in layers]
				if len(layers) == 1:
					print('%5d %-6s %d' % (ind, 'route', layers[0]))
					prev_width = out_widths[layers[0]]
					prev_height = out_heights[layers[0]]
					prev_filters = out_filters[layers[0]]
				elif len(layers) == 2:
					print('%5d %-6s %d %d' % (ind, 'route', layers[0], layers[1]))
					prev_width = out_widths[layers[0]]
					prev_height = out_heights[layers[0]]
					prev_filters = out_filters[layers[0]] + out_filters[layers[1]]
					assert(prev_width == out_widths[layers[1]])
					assert(prev_height == out_heights[layers[1]])
				out_filters.append(prev_filters)
				out_heights.append(prev_height)
				out_widths.append(prev_width)
			elif block['layer_type'] in ['region', 'yolo', 'detection']:
				print('%5d %-6s' % (ind, 'detection'))
				out_filters.append(prev_filters)
				out_heights.append(prev_height)
				out_widths.append(prev_width)
			elif block['layer_type'] == 'shortcut':
				from_id = int(block['from'])
				from_id = from_id if from_id > 0 else from_id + ind
				print('%5d %-6s %d' % (ind, 'shortcut', from_id))
				prev_width = out_widths[from_id]
				prev_height = out_heights[from_id]
				prev_filters = out_filters[from_id]
				out_widths.append(prev_width)
				out_heights.append(prev_height)
				out_filters.append(prev_filters)
			elif block['layer_type'] == 'connected':
				width, height = 1, 1
				filters = int(block['output'])
				print('%5d %-6s                             %d  ->  %3d' % (ind, 'connected', prev_filters,  filters))
				prev_width, prev_height, prev_filters = width, height, filters
				out_widths.append(prev_width)
				out_heights.append(prev_height)
				out_filters.append(prev_filters)
			elif block['layer_type'] == 'dropout':
				print('%5d %-6s' % (ind, 'dropout'))
				out_filters.append(prev_filters)
				out_heights.append(prev_height)
				out_widths.append(prev_width)
			else:
				print('[Error]:unkown layer_type <%s>...' % (block['layer_type']))
				sys.exit(0)
# ----------------------------------------------------------------------------------------------------------------------------------


'''
Function:
	data load/save
'''
# ----------------------------------------------------------------------------------------------------------------------------------
# load conv data without bn
def load_conv(buf, start, conv_model):
	num_w = conv_model.weight.numel()
	num_b = conv_model.bias.numel()
	conv_model.bias.data.copy_(torch.from_numpy(buf[start: start+num_b]))
	start = start + num_b
	conv_model.weight.data.copy_(torch.from_numpy(buf[start: start+num_w]))
	start = start + num_w
	return start
# save conv data without bn
def save_conv(fp, conv_model):
	if conv_model.bias.is_cuda:
		convert2cpu(conv_model.bias.data).numpy().tofile(fp)
		convert2cpu(conv_model.weight.data).numpy().tofile(fp)
	else:
		conv_model.bias.data.numpy().tofile(fp)
		conv_model.weight.data.numpy().tofile(fp)

# load conv data with bn
def load_conv_bn(buf, start, conv_model, bn_model):
	num_w = conv_model.weight.numel()
	num_b = bn_model.bias.numel()
	bn_model.bias.data.copy_(torch.from_numpy(buf[start: start+num_b]))
	start = start + num_b
	bn_model.weight.data.copy_(torch.from_numpy(buf[start: start+num_b]))
	start = start + num_b
	bn_model.running_mean.copy_(torch.from_numpy(buf[start: start+num_b]))
	start = start + num_b
	bn_model.running_var.copy_(torch.from_numpy(buf[start: start+num_b]))
	start = start + num_b
	conv_model.weight.data.copy_(torch.from_numpy(buf[start: start+num_w]))
	start = start + num_w
	return start
# save conv data with bn
def save_conv_bn(fp, conv_model, bn_model):
	if bn_model.bias.is_cuda:
		convert2cpu(bn_model.bias.data).numpy().tofile(fp)
		convert2cpu(bn_model.weight.data).numpy().tofile(fp)
		convert2cpu(bn_model.running_mean).numpy().tofile(fp)
		convert2cpu(bn_model.running_var).numpy().tofile(fp)
		convert2cpu(conv_model.weight.data).numpy().tofile(fp)
	else:
		bn_model.bias.data.numpy().tofile(fp)
		bn_model.weight.data.numpy().tofile(fp)
		bn_model.running_mean.numpy().tofile(fp)
		bn_model.running_var.numpy().tofile(fp)
		conv_model.weight.data.numpy().tofile(fp)

# load fc data
def load_fc(buf, start, fc_model):
	num_w = fc_model.weight.numel()
	num_b = fc_model.bias.numel()
	fc_model.bias.data.copy_(torch.from_numpy(buf[start: start+num_b]))
	start = start + num_b
	fc_model.weight.data.copy_(torch.from_numpy(buf[start: start+num_w]))
	start = start + num_w
	return start
# save fc data
def save_fc(fp, fc_model):
	fc_model.bias.data.numpy().tofile(fp)
	fc_model.weight.data.numpy().tofile(fp)
# ----------------------------------------------------------------------------------------------------------------------------------


'''
Function:
	convert GPU -> CPU
'''
# ----------------------------------------------------------------------------------------------------------------------------------
# Float
def convert2cpu(gpu_matrix):
	return torch.FloatTensor(gpu_matrix.size()).copy_(gpu_matrix)
# Long
def convert2cpu_long(gpu_matrix):
	return torch.LongTensor(gpu_matrix.size()).copy_(gpu_matrix)
# ----------------------------------------------------------------------------------------------------------------------------------


'''
Function:
	count file lines
	refer: https://www.safaribooksonline.com/library/view/python-cookbook/0596001673/ch04s07.html
'''
# ----------------------------------------------------------------------------------------------------------------------------------
def file_lines(thefilepath):
	count = 0
	thefile = open(thefilepath, 'rb')
	while True:
		buf = thefile.read(8192*1024)
		if not buf:
			break
		try:
			count += buf.count('\n')
		except:
			count += buf.count(b'\n')
	thefile.close()
	return count
# ----------------------------------------------------------------------------------------------------------------------------------


'''
Function:
	Determine the image type of fhandle and return its size. from draco
	refer: https://stackoverflow.com/questions/8032642/how-to-obtain-image-size-using-standard-python-class-without-using-external-lib
'''
# ----------------------------------------------------------------------------------------------------------------------------------
def get_image_size(fname):
	import struct
	import imghdr
	with open(fname, 'rb') as fhandle:
		head = fhandle.read(24)
		if len(head) != 24: 
			return
		if imghdr.what(fname) == 'png':
			check = struct.unpack('>i', head[4: 8])[0]
			if check != 0x0d0a1a0a:
				return
			width, height = struct.unpack('>ii', head[16: 24])
		elif imghdr.what(fname) == 'gif':
			width, height = struct.unpack('<HH', head[6: 10])
		elif imghdr.what(fname) == 'jpeg' or imghdr.what(fname) == 'jpg':
			try:
				# Read 0xff next
				fhandle.seek(0)
				size = 2
				ftype = 0
				while not 0xc0 <= ftype <= 0xcf:
					fhandle.seek(size, 1)
					byte = fhandle.read(1)
					while ord(byte) == 0xff:
						byte = fhandle.read(1)
					ftype = ord(byte)
					size = struct.unpack('>H', fhandle.read(2))[0] - 2
				# We are at a SOFn block
				# Skip `precision' byte.
				fhandle.seek(1, 1)
				height, width = struct.unpack('>HH', fhandle.read(4))
			#IGNORE:W0703
			except Exception:
				return
		else:
			return
		return width, height
# ----------------------------------------------------------------------------------------------------------------------------------


'''
Function:
	Sigmoid and softmax
'''
# ----------------------------------------------------------------------------------------------------------------------------------
def sigmoid(x):
	return 1.0/(math.exp(-x)+1.)

def softmax(x):
	x = torch.exp(x - torch.max(x))
	x = x / x.sum()
	return x
# ----------------------------------------------------------------------------------------------------------------------------------


'''
Function:
	Compute iou.
	IOU = Overlapping area / (two boxes' total area - Overlapping area)
	Range: 0 - 1
	About x1y1x2y2: determine the box data format.
'''
# ----------------------------------------------------------------------------------------------------------------------------------
# for one
def bbox_iou(box1, box2, x1y1x2y2=True):
	if x1y1x2y2:
		mx = min(box1[0], box2[0])
		Mx = max(box1[2], box2[2])
		my = min(box1[1], box2[1])
		My = max(box1[3], box2[3])
		w1 = box1[2] - box1[0]
		h1 = box1[3] - box1[1]
		w2 = box2[2] - box2[0]
		h2 = box2[3] - box2[1]
	else:
		mx = min(box1[0]-box1[2]/2.0, box2[0]-box2[2]/2.0)
		Mx = max(box1[0]+box1[2]/2.0, box2[0]+box2[2]/2.0)
		my = min(box1[1]-box1[3]/2.0, box2[1]-box2[3]/2.0)
		My = max(box1[1]+box1[3]/2.0, box2[1]+box2[3]/2.0)
		w1 = box1[2]
		h1 = box1[3]
		w2 = box2[2]
		h2 = box2[3]
	uw = Mx - mx
	uh = My - my
	cw = w1 + w2 - uw
	ch = h1 + h2 - uh
	if cw <= 0 or ch <= 0:
		return 0.0
	area1 = w1 * h1
	area2 = w2 * h2
	carea = cw * ch
	uarea = area1 + area2 - carea
	return carea / uarea
# for many
def bbox_ious(boxes1, boxes2, x1y1x2y2=True):
	if x1y1x2y2:
		mx = torch.min(boxes1[0], boxes2[0])
		Mx = torch.max(boxes1[2], boxes2[2])
		my = torch.min(boxes1[1], boxes2[1])
		My = torch.max(boxes1[3], boxes2[3])
		w1 = boxes1[2] - boxes1[0]
		h1 = boxes1[3] - boxes1[1]
		w2 = boxes2[2] - boxes2[0]
		h2 = boxes2[3] - boxes2[1]
	else:
		mx = torch.min(boxes1[0]-boxes1[2]/2.0, boxes2[0]-boxes2[2]/2.0)
		Mx = torch.max(boxes1[0]+boxes1[2]/2.0, boxes2[0]+boxes2[2]/2.0)
		my = torch.min(boxes1[1]-boxes1[3]/2.0, boxes2[1]-boxes2[3]/2.0)
		My = torch.max(boxes1[1]+boxes1[3]/2.0, boxes2[1]+boxes2[3]/2.0)
		w1 = boxes1[2]
		h1 = boxes1[3]
		w2 = boxes2[2]
		h2 = boxes2[3]
	uw = Mx - mx
	uh = My - my
	cw = w1 + w2 - uw
	ch = h1 + h2 - uh
	mask = ((cw <= 0) + (ch <= 0) > 0)
	area1 = w1 * h1
	area2 = w2 * h2
	carea = cw * ch
	carea[mask] = 0
	uarea = area1 + area2 - carea
	return carea/uarea
# ----------------------------------------------------------------------------------------------------------------------------------


'''
Function:
	print function.
'''
# ----------------------------------------------------------------------------------------------------------------------------------
def logging(message):
	print('%s %s' % (time.strftime("%Y-%m-%d %H:%M:%S", time.localtime()), message))
# ----------------------------------------------------------------------------------------------------------------------------------


'''
Function:
	non maximum suppression.
	boxes: [x, y, w, h, det_conf, cls_max_conf, cls_max_id]
'''
# ----------------------------------------------------------------------------------------------------------------------------------
def nms(boxes, nms_thresh):
	if len(boxes) == 0:
		return boxes
	det_confs = torch.zeros(len(boxes))
	for i in range(len(boxes)):
		det_confs[i] = boxes[i][4]
	# descending
	_, sortIds = torch.sort(det_confs, descending=True)
	out_boxes = []
	for i in range(len(boxes)):
		box_i = boxes[sortIds[i]]
		if box_i[4] > 0:
			out_boxes.append(box_i)
			for j in range(i+1, len(boxes)):
				box_j = boxes[sortIds[j]]
				if bbox_iou(box_i, box_j, x1y1x2y2=False) > nms_thresh:
					box_j[4] = 0
	return out_boxes	
# ----------------------------------------------------------------------------------------------------------------------------------


'''
Function:
	load class names
'''
# ----------------------------------------------------------------------------------------------------------------------------------
def load_class_names(namesfile):
	class_names = []
	with open(namesfile, 'r') as fp:
		lines = fp.readlines()
	for line in lines:
		line = line.rstrip()
		class_names.append(line)
	return class_names
# ----------------------------------------------------------------------------------------------------------------------------------


'''
Function:
	read the ground truth data.
Input:
	-lab_path: the path of labels.
	-min_box_scale: min scale of the predict boxes.
	-is_changed: whether need to change the label or not.
'''
# ----------------------------------------------------------------------------------------------------------------------------------
def read_truths(lab_path, **kwargs):
	min_box_scale = kwargs.get('min_box_scale')
	is_changed = kwargs.get('is_changed')
	if not os.path.exists(lab_path):
		return np.array([])
	if os.path.getsize(lab_path):
		truths = np.loadtxt(lab_path)
		truths = truths.reshape(truths.size//5, 5)
		if is_changed:
			new_truths = []
			for i in range(truths.shape[0]):
				if truths[i][3] < min_box_scale:
					continue
				new_truths.append([truths[i][0], truths[i][1], truths[i][2], truths[i][3], truths[i][4]])
			return new_truths
		return truths
	else:
		return np.array([])
# ----------------------------------------------------------------------------------------------------------------------------------


'''
Function:
	for data augmentation.
'''
# ----------------------------------------------------------------------------------------------------------------------------------
# adjust scale in a specified channel.
def scale_image_channel(im, c, v):
	cs = list(im.split())
	cs[c] = cs[c].point(lambda i: i * v)
	out = Image.merge(im.mode, tuple(cs))
	return out

# distort image in hsv space.(hue, saturation, value)
def distort_image(im, hue, sat, val):
	im = im.convert('HSV')
	cs = list(im.split())
	cs[1] = cs[1].point(lambda i: i * sat)
	cs[2] = cs[2].point(lambda i: i * val)
	def change_hue(x):
		x += hue*255
		if x > 255:
			x -= 255
		if x < 0:
			x += 255
		return x
	cs[0] = cs[0].point(change_hue)
	im = Image.merge(im.mode, tuple(cs))
	im = im.convert('RGB')
	return im

# generate random scale.
def rand_scale(s):
	scale = random.uniform(1, s)
	if random.randint(1, 10000) % 2:
		return scale
	return 1.0 / scale

# generate random hue, saturation, exposure, and then distort image in hsv space.
def random_distort_image(im, hue, saturation, exposure):
	dhue = random.uniform(-hue, hue)
	dsat = rand_scale(saturation)
	dexp = rand_scale(exposure)
	res = distort_image(im, dhue, dsat, dexp)
	return res

# data augmentation
def data_augmentation(img, shape, jitter, hue, saturation, exposure):
	oh = img.height
	ow = img.width
	dw = int(ow*jitter)
	dh = int(oh*jitter)
	pleft = random.randint(-dw, dw)
	pright = random.randint(-dw, dw)
	ptop = random.randint(-dh, dh)
	pbot = random.randint(-dh, dh)
	swidth = ow - pleft - pright
	sheight = oh - ptop - pbot
	sx = float(swidth) / ow
	sy = float(sheight) / oh
	dx = (float(pleft) / ow) / sx
	dy = (float(ptop) / oh) / sy
	cropped = img.crop((pleft, ptop, pleft+swidth-1, ptop+sheight-1))
	sized = cropped.resize(shape)
	flip = random.randint(1, 10000) % 2
	if flip:
		sized = sized.transpose(Image.FLIP_LEFT_RIGHT)
	img = random_distort_image(sized, hue, saturation, exposure)
	return img, flip, dx, dy, sx, sy

# get modified label after data augmentation.
def modify_truth_detection(labpath, flip, dx, dy, sx, sy, max_object):
	label = np.zeros((max_object, 5))
	if os.path.getsize(labpath):
		bs = np.loadtxt(labpath)
		if bs is None:
			return label
		bs = np.reshape(bs, (-1, 5))
		cc = 0
		for i in range(bs.shape[0]):
			x1 = bs[i][1] - bs[i][3]/2
			y1 = bs[i][2] - bs[i][4]/2
			x2 = bs[i][1] + bs[i][3]/2
			y2 = bs[i][2] + bs[i][4]/2
			x1 = min(0.999, max(0, x1 * sx - dx))
			y1 = min(0.999, max(0, y1 * sy - dy))
			x2 = min(0.999, max(0, x2 * sx - dx))
			y2 = min(0.999, max(0, y2 * sy - dy))
			bs[i][1] = (x1 + x2) / 2
			bs[i][2] = (y1 + y2) / 2
			bs[i][3] = (x2 - x1)
			bs[i][4] = (y2 - y1)
			if flip:
				bs[i][1] = 0.999 - bs[i][1]
			if bs[i][3] < 0.001 or bs[i][4] < 0.001:
				continue
			label[cc] = bs[i]
			cc += 1
	label = np.reshape(label, (-1))
	return label

# load detection data after data augmentation
def load_detection_daug(imgpath, labpath, shape, jitter, hue, saturation, exposure, **kwargs):
	max_object = kwargs.get('max_object')
	if not max_object:
		max_object = 50
	img = Image.open(imgpath).convert('RGB')
	img, flip, dx, dy, sx, sy = data_augmentation(img, shape, jitter, hue, saturation, exposure)
	label = modify_truth_detection(labpath, flip, dx, dy, 1./sx, 1./sy, max_object=max_object)
	return img, label
# ----------------------------------------------------------------------------------------------------------------------------------


'''
Function:
	Get all boxes by using the outputs of network.
'''
# ----------------------------------------------------------------------------------------------------------------------------------

# ----------------------------------------------------------------------------------------------------------------------------------





# for test
if __name__ == '__main__':
	cfgfile = r'C:\Users\ThinkPad\Desktop\OD_baseyolo\cfg\yolov1.cfg'
	CfgParser().parser(cfgfile, is_print=True)