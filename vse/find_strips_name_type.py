#!/usr/bin/python
import bpy
import re
import time

##
## Find and display relevant media sequence strips from the Blender VSE
##
## Built to catalog assets and display them for copyright/fair use documentation.
##
## Author: GitHub user Botmasher (Joshua R)
##
##	0) locate the run function at the bottom
## 	1) build a list of strip types to search for (SOUND, IMAGE, MOVIE)
## 	2) build a dictionary of per-type text to ignore while searching through names
## 	3) call the run function, passing in:
## 		- your list of strip types to search
## 		- your dictionary or per-type text/regexes to ignore
## 		- optionally, ignore_duplication=False to include duplication suffixes generated by Blender VSE
## 	4) run this script in Blender
## 	--- the run function will then take these steps ---
## 	5) call build_ignored_names_re to turn the ignored text into a regular expression
## 		- optionally pass array of regular expressions to avoid
## 		- I currently separate out calls from the for loop to pass specific regexes for each sequence type
##	6) call find_sequence_names to search through sequences
## 		- pass in any sequence_editor to search through all of its sequences
## 		- or check that the scene has a sequence_editor (VSE) before calling
## 		- pass through the built ignored regexes by type and the desired sequence types
## 	7) call print_sequence_names to output the names to console (shell if running Blender through prompt)
## 		- set ignore_duplication=False to list duplicates as well (e.g. myaudio.001, myaudio.002)
##

# TODO use file path and name to vet duplicates
# TODO take documentation from above and include within multiline comments
# TODO add ability to pass ignored_res_list into run function

def build_ignored_names_re(namestrings, ignored_res_list):
	"""Build regular expression to successively filter out object names"""
	if namestrings is None or len(namestrings) < 1:
		if ignored_res_list == []: return None
		ignored_re = "|".join(regex.pattern for regex in ignored_res_list)
		return ignored_re
	ignored_namestring = namestrings.pop()
	ignored_res_list.append(re.compile(".*%s.*" % re.escape(ignored_namestring)))
	return build_ignored_names_re(namestrings, ignored_res_list)

def find_sequence_names(sequencer=bpy.context.scene.sequence_editor, sequence_types=["SOUND", "MOVIE", "IMAGE"], ignored_res_dict={}):
	"""Build a dictionary of sequence lists by type from all sequencer strips that filter through ignored regexes"""
	if sequencer is None:
		print("Error finding sequence names: SEQUENCE_EDITOR not found")
		return None
	found_sequences = {sequence_type: [] for sequence_type in sequence_types}
	for sequence in sequencer.sequences:
		if sequence.type in sequence_types and (ignored_res_dict[sequence.type] is None or not re.match(ignored_res_dict[sequence.type], sequence.name)):
			found_sequences[sequence.type].append(sequence)
	return found_sequences

def print_sequence_names(sequences_by_type, ignore_duplication=True):
	"""Output the name of each sequence in a dictionary of sequences by type,
	optionally ignoring unique Blender duplication suffix"""
	ignore_mssg = "ignored" if ignore_duplication else "included"
	print("\nFound Sequences (duplicates %s):" % ignore_mssg)
	if ignore_duplication:
		suffix_re = re.compile(r"(\.\d{3})+")
		# store and print cleaned names with any duplicate suffix (.nnn) removed
		for sequence_type in sequences_by_type:
			split_names = set()
			print("\n{0} strips:".format(sequence_type))
			for sequence in sequences_by_type[sequence_type]:
				suffix_match = suffix_re.search(sequence.name)
				if suffix_match is not None:
					suffix_i = suffix_match.start()
					split_names.add(sequence.name[:suffix_i])
				else:
					split_names.add(sequence.name)
			if len(split_names) < 1:
				print("(0 sequences found)")
			else:
				for name in split_names: print(name)
	else:
		# print all passed-in names
		for sequence_type in sequences_by_type:
			for sequence in sequences_by_type[sequence_type]:
				print("%s sequence: %s" % (sequence.type, sequence.name))
	return {'FINISHED'}

def run_strip_finder(sequence_types=['IMAGE', 'MOVIE', 'SOUND'], ignored_names={}, ignore_duplication=True):
	"""Print strip names per requested sequence type where names are filtered through ignored strings per type"""
	# build regexes of names to ignore
	if sequence_types == []:
		print("0 sequences found - no sequence types provided.")
		return
	for sequence_type in sequence_types:
		if sequence_type in ignored_names.keys():
			ignored_names[sequence_type] = build_ignored_names_re(ignored_names[sequence_type], [])
		else:
			ignored_names[sequence_type] = None
	print(ignored_names)
	# find sequences
	sequences = find_sequence_names(ignored_res_dict=ignored_names, sequence_types=sequence_types)
	# display names
	print_sequence_names(sequences, ignore_duplication=ignore_duplication)

run_strip_finder(sequence_types=['SOUND'], ignored_names={'SOUND': ["audio-"], 'MOVIE': [], 'IMAGE': []})
