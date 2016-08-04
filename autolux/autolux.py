#!/usr/bin/env python
# required utilities: imagemagick, xdotool, xbacklight

import time
import os
import shlex, subprocess


# BRIGHTNESS LEVELS (should be between 1 and 100)
MIN_LEVEL=5
MAX_LEVEL=20

# interpolate over our threshold (should be between 1 and 65K)
MAX_BRIGHT=50000
MIN_BRIGHT=5000

# interval between screenshots
SLEEP_TIME=1200
TRANSITION_MS=800
RECALIBRATE_MS=60 * 1000

# EXAMPLE: 100x200+300+400
# 100 width, 200 height, 300 offset from left, 400 offset from top
CROP_SCREEN="10x100%+400+0"

SCREENSHOT_CMD='import -colorspace gray -screen -w root -quality 20'
BRIGHTNESS_CMD='-format "%[mean]" info:'

# change brightness when PID changes or
# change brightness when window changes
CHECK_PID=False
CHECK_PID_CMD='xdotool getwindowfocus getwindowpid'
# change brightness when window name changes
CHECK_TITLE_CMD='xdotool getwindowfocus getwindowname'

CALIBRATION_MODE=False

VERBOSE=False
def load_options():
  global MIN_LEVEL, MAX_LEVEL, MAX_BRIGHT, MIN_BRIGHT, CROP_SCREEN
  global SLEEP_TIME, TRANSITION_MS, RECALIBRATE_MS
  global VERBOSE, CHECK_PID, CALIBRATION_MODE

  from optparse import OptionParser
  parser = OptionParser()
  parser.add_option("--min-level", dest="min_level", type="int", default=MIN_LEVEL,
    help="min brightness level (from 1 to 100, default is %s)" % MIN_LEVEL)
  parser.add_option("--max-level", dest="max_level", type="int", default=MAX_LEVEL,
    help="max brightness level (from 1 to 100, default is %s)" % MAX_LEVEL)
  parser.add_option("--interval", dest="interval", type="int", default=SLEEP_TIME,
    help="take screen snapshot every INTERVAL ms and readjust the screen brightness, default is %s" % SLEEP_TIME)
  parser.add_option("--min-bright", dest="min_bright", type="int", default=MIN_BRIGHT,
    help="upper brightness threshold before setting screen to lowest brightness (45K to 65K, default is %s)" % MIN_BRIGHT)
  parser.add_option("--max-bright", dest="max_bright", type="int", default=MAX_BRIGHT,
  help="lower brightness threshold before setting screen to highest brightness (1K to 15K, default is %s)" % MIN_BRIGHT)
  parser.add_option("--recalibrate-time", dest="recalibrate", type="int",
    default=RECALIBRATE_MS, help="ms before recalibrating even if the window hasn't changed. set to 0 to disable, default is 60K")
  parser.add_option("--fade-time", dest="fade_time", type="int", default=TRANSITION_MS,
    help="time to fade backlight in ms, default is %s" % TRANSITION_MS)
  parser.add_option("--crop", dest="crop_screen", type='str', default=CROP_SCREEN,
    help="area to inspect, use imagemagick geometry style string (f.e. 50%x20%+400+100 means 50% width, 20% height at offset 400x and 100y)")
  parser.add_option("--verbose", dest="verbose", action="store_true", help="turn on verbose output, including screenshot timing info")
  parser.add_option("--pid", dest="check_pid", action="store_true", help="check screen brightness when PID changes")
  parser.add_option("--title", dest="check_pid", action="store_false", help="check screen brightness when window changes")
  parser.add_option("--clog", dest="calibrate", action="store_true", help="add calibration logging")


  options, args = parser.parse_args()
  MIN_LEVEL = options.min_level
  MAX_LEVEL = options.max_level
  SLEEP_TIME = options.interval
  MAX_LEVEL = options.max_level
  TRANSITION_MS = options.fade_time
  CROP_SCREEN = options.crop_screen
  VERBOSE = options.verbose
  RECALIBRATE_MS = options.recalibrate
  CHECK_PID = options.check_pid
  CALIBRATION_MODE=options.calibrate

  global SCREENSHOT_CMD
  if CROP_SCREEN is not None:
    SCREENSHOT_CMD += ' -crop %s' % CROP_SCREEN

  print "SCREENSHOT CMD", SCREENSHOT_CMD




def print_config():
  print "CROPPING:", not not CROP_SCREEN
  print "FADE TIME:", TRANSITION_MS
  print "SLEEP TIME:", SLEEP_TIME
  print "DISPLAY RANGE:", MIN_LEVEL, MAX_LEVEL
  print "BRIGHTNESS RANGE:", MIN_BRIGHT, MAX_BRIGHT
  print "CALIBRATION LOG:", CALIBRATION_MODE
  print "RECALIBRATE EVERY:", RECALIBRATE_MS
  print "FOLLOW WINDOW PID:", not not CHECK_PID
  print "FOLLOW WINDOW TITLE:", not CHECK_PID

def run_cmd(cmd, bg=False):
  args = shlex.split(cmd)
  start = int(round(time.time() * 1000))
  ret = ""
  if not bg:
    ret = subprocess.check_output(args)
  else:
    subprocess.Popen(args)

  end = int(round(time.time() * 1000))
  if VERBOSE:
    print "TIME:", end - start, "CMD", cmd.split()[0]
  return ret

def monitor_luma():
  prev_brightness = None
  prev_window = None
  prev_mean = None

  cur_range = MAX_BRIGHT - MIN_BRIGHT
  suppressed_time = 0

  last_calibrate = int(time.time())


  while True:
    time.sleep(SLEEP_TIME / 1000.0)

    focused_cmd = CHECK_TITLE_CMD
    if CHECK_PID:
      focused_cmd = CHECK_PID_CMD

    try: window = run_cmd(focused_cmd)
    except: window = None

    if prev_window == window:
      suppressed_time += SLEEP_TIME / 1000

      if CALIBRATION_MODE:
        now = int(time.time())
        cur_bright = float(run_cmd("xbacklight -get"))
        if abs(prev_brightness - cur_bright) > 1 and now - last_calibrate > next_calibrate:
          print "USER|TS:%s, LUMA:%05i, CUR:%.02f, EXP:%s" % (now, prev_mean, cur_bright, prev_brightness)
          next_calibrate = min(2*next_calibrate, RECALIBRATE_MS / 1000)
          last_calibrate = now

      if RECALIBRATE_MS > 0 and suppressed_time < RECALIBRATE_MS:
          continue
      print "RECALIBRATING BRIGHTNESS AFTER %S ms" % RECALIBRATE_MS

    suppressed_time = 0
    next_calibrate = 1

    try: window = run_cmd(focused_cmd)
    except: window = None
    prev_window = window

    brightness = run_cmd(SCREENSHOT_CMD + " " + BRIGHTNESS_CMD)


    try:
      cur_mean = float(brightness)
    except Exception, e:
      print "ERROR GETTING MEAN LUMA", e
      continue


    trimmed_mean = max(min(MAX_BRIGHT, cur_mean), MIN_BRIGHT) - MIN_BRIGHT
    trimmed_mean = int(trimmed_mean / 500) * 500
    range_is = float(trimmed_mean) / float(cur_range)

    new_gamma = 1 - range_is
    new_level =  (MAX_LEVEL - MIN_LEVEL) * new_gamma + MIN_LEVEL

    prev_mean = trimmed_mean

    new_level = round(new_level) 
    if prev_brightness != new_level:
      now = int(time.time())
      print "MODEL|TS:%s," % now, "LUMA:%05i," % trimmed_mean, "NEW GAMMA:%.02f," % new_gamma, "NEW BRIGHTNESS:", "%s/%s" % (int(new_level), MAX_LEVEL)
      run_cmd("xbacklight -set %s -time %s" % (new_level, TRANSITION_MS))
    prev_brightness = new_level

def run():
  load_options()
  print_config()
  monitor_luma()

if __name__ == "__main__":
  run()
