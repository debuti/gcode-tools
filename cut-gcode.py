#!/usr/bin/env python3
#!/usr/bin/env python
###############################################################################################
#  Author: 
__author__ = 'debuti@gmail.com'
# Program: 
__program__ = 'cut-gcode'
# Descrip: 
__desc__ = '''Process GCode and cut at traveling points. Useful to resume a failed job'''
# Version: 
__version__ = '0.0.1'
#    Date:
__date__ = '20200915'
# License: Propietary
# History: 
#          0.0.1 (20200915)
#            -Initial release.
#            -Tested against CAMBAM gcode
###############################################################################################
# https://marlinfw.org/meta/gcode/

import argparse
import sys

FORMAT="{:50} ({:<10.10} {})"
CHECKPOINT_TAG="(--CHECKPOINT!--)"

try:
  from pygcode import Line, Machine, GCodeRapidMove, GCodeAbsoluteDistanceMode, GCodeIncrementalDistanceMode, GCodeFeedRate
except:
  print("pygcode not found. Install with: python -m pip install pygcode")
  sys.exit(-1)

def getClearanceHeight(gcodes):
  m = Machine()  
  last = m.pos
  clearance_height = m.pos._value['Z']
  for gcode in gcodes:
    m.process_gcodes(gcode['gcode'])
    if clearance_height < m.pos._value['Z']: clearance_height = m.pos._value['Z']
  return clearance_height
  
def list(args, gcodes, clearance_height):
  m = Machine()
  print("The line numbers where a cut is possible are:")
  for gcode in gcodes:
    m.process_gcodes(gcode['gcode'])
    if clearance_height == m.pos._value['Z']:
      print("  {:7} at {:6.2f}% in {}".format(gcode["line_no"], gcode["line_no"]*100/gcodes[-1]["line_no"],m.pos))

def cut(args, gcodes, clearance_height):
  non_motion = []
  
  # Select where to cut
  m = Machine()
  last = m.pos
  checkpoint = {'gcode': None, 'pos': m.pos, 'mode': m.mode.distance}
  for idx, gcode in enumerate(gcodes):
    m.process_gcodes(gcode['gcode'])
    if gcode["line_no"] > args.line:
      break
    if m.pos == last: non_motion.append(gcode)
    last = m.pos
    if clearance_height == m.pos._value['Z']:
      checkpoint = {'idx': idx, 'gcode': gcode, 'pos': m.pos, 'mode': m.mode.distance}
      
  #print("Checkpoint at {}".format(checkpoint))
  
  # If the user wants to cut before the first clearance height, do nothing
  if checkpoint['gcode'] is None:
    print("The provided line is not a valid one, use list subcommand for more info. Exiting")
    return
    
  # Dump the non motion commands first
  for gcode in non_motion:
   # if not isinstance(gcode['gcode'], GCodeFeedRate):  # Ignore feedrates please
      print(FORMAT.format(str(gcode['gcode']), str(gcode['line_no']), gcode['gcode'].__class__.__name__), file=args.output)
   
  # Insert the travel until the checkpoint position
  gcode = GCodeAbsoluteDistanceMode()
  print(FORMAT.format(str(gcode), "Cut comp.", gcode.__class__.__name__), file=args.output)
  gcode = GCodeRapidMove(Z=clearance_height)
  print(FORMAT.format(str(gcode), "Cut comp.", gcode.__class__.__name__), file=args.output)
  gcode = GCodeRapidMove(X=checkpoint['pos']._value['X'], Y=checkpoint['pos']._value['Y'], Z=checkpoint['pos']._value['Z'])
  print(FORMAT.format(str(gcode), "Cut comp.", gcode.__class__.__name__), file=args.output)
  gcode = checkpoint['mode']
  print(FORMAT.format(str(gcode), "Cut comp.", gcode.__class__.__name__), file=args.output)
  print(CHECKPOINT_TAG, file=args.output)
      
  # Dump the rest of the codes from the original file (to preserve formatting)
  try: 
    args.input.seek(gcodes[checkpoint['idx']+1]['offset'])
    for line in args.input:
      print(line, file=args.output, end="")
  except: pass
  
  if args.verify:
    s = Machine()
    t = Machine()
    
    # Run input gcodes until the selected
    for gcode in gcodes[:checkpoint['idx']+1]:
      s.process_gcodes(gcode['gcode'])
    
    # Run output gcodes until checkpoint
    args.output.seek(0)
    line = args.output.readline()
    while line:
      if CHECKPOINT_TAG in line:
        break
      for gcode in Line(line).block.gcodes:
        t.process_gcodes(gcode)
      line = args.output.readline()

    args.input.seek(gcodes[checkpoint['idx']+1]['offset'])
    sline = args.output.readline()
    tline = args.input.readline()
    while sline and tline:
      for gcode in Line(sline).block.gcodes: s.process_gcodes(gcode)
      for gcode in Line(tline).block.gcodes: t.process_gcodes(gcode)
      if s.pos!=t.pos:
        print("\nOutput gcode not verified (source: {}, target: {})".format(s.pos, t.pos))
        return
      sline = args.output.readline()
      tline = args.input.readline()
        
    print("\nOutput gcode verified")
  
def main(args):
  gcodes = []
  offset = 0
  line_no = 0
  line = args.input.readline()
  while line:
    for gcode in Line(line).block.gcodes:
      gcodes.append({'line_no': line_no+1, 'offset':offset, 'line': line, 'gcode':gcode,})
    offset = args.input.tell()
    line_no+=1
    line = args.input.readline()
    
  clearance_height = getClearanceHeight(gcodes)
  print("GCode Z clearance_height is {}".format(clearance_height))
  
  if args.command=="list": list(args, gcodes, clearance_height)
      
  if args.command=="cut":  cut(args, gcodes, clearance_height)
    

if __name__=="__main__":
  parser = argparse.ArgumentParser(prog=__program__, description=__desc__)
  parser.add_argument('-i', '--input', type=argparse.FileType('r'), required=True,
                      help='Input gcode file')

  subparsers = parser.add_subparsers(help='Sub-command help', dest='command', required=True)
  
  list_subparser = subparsers.add_parser("list", description="List available cut-points")

  cut_subparser = subparsers.add_parser("cut", description="Cut gcode at cut-point")  
  cut_subparser.add_argument('-o', '--output', type=argparse.FileType('w+'),
                      required=('-v' in sys.argv or '--verify' in sys.argv),
                      help='Output gcode file')
  cut_subparser.add_argument('-l', '--line', type=int, required=True,
                      help='Line selector. The output file will be cutted at this position')
  cut_subparser.add_argument('-v', '--verify', action='store_true', 
                      help='Verify the machine movement against the source')
  main(parser.parse_args())
  