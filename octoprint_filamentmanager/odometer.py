# coding=utf-8
from __future__ import absolute_import

__author__ = "Sven Lohrmann <malnvenshorn@gmail.com> based on work by Gina Häußge <osd@foosel.net>"
__license__ = "GNU Affero General Public License http://www.gnu.org/licenses/agpl.html"
__copyright__ = "Copyright (C) 2017 Sven Lohrmann - Released under terms of the AGPLv3 License"

import math
import re


class FilamentOdometer(object):

    regexE = re.compile(r'.*E(-?\d+(\.\d+)?)')
    regexT = re.compile(r'[tT](\d+)')
    regexD = re.compile(r'[dD](\d+(\.\d+)?)')

    def __init__(self, g90_extruder):
        self.g90_extruder = g90_extruder
        self.reset()

    def reset(self):
        self.relativeMode = False
        self.relativeExtrusion = False
        self.lastExtrusion = [0.0]
        self.totalExtrusion = [0.0]
        self.maxExtrusion = [0.0]
        self.currentTool = 0
        self.volumetricExtrusion = [False]
        self.filamentDiametersByM200 = [1.75]
        self._baseAreas = [self._calc_base_area(1.75)]  # save base areas for less computations while printing

    def reset_extruded_length(self):
        tools = len(self.maxExtrusion)
        self.maxExtrusion = [0.0] * tools
        self.totalExtrusion = [0.0] * tools

    def parse(self, gcode, cmd):
        if gcode == "G1" or gcode == "G0":  # move
            e = self._get_float(cmd, self.regexE)
            if e is not None:
                if self.volumetricExtrusion[self.currentTool]:
                    # if volumetric extrusion is active for current tool convert volume to mm
                    e = e / self._baseAreas[self.currentTool]

                if self.relativeMode or self.relativeExtrusion:
                    # e is already relative, nothing to do
                    pass
                else:
                    e -= self.lastExtrusion[self.currentTool]
                self.totalExtrusion[self.currentTool] += e
                self.lastExtrusion[self.currentTool] += e
                self.maxExtrusion[self.currentTool] = max(self.maxExtrusion[self.currentTool],
                                                          self.totalExtrusion[self.currentTool])
        elif gcode == "G90":  # set to absolute positioning
            self.relativeMode = False
            if self.g90_extruder:
                self.relativeExtrusion = False
        elif gcode == "G91":  # set to relative positioning
            self.relativeMode = True
            if self.g90_extruder:
                self.relativeExtrusion = True
        elif gcode == "G92":  # set position
            e = self._get_float(cmd, self.regexE)
            if e is not None:
                self.lastExtrusion[self.currentTool] = e
        elif gcode == "M82":  # set extruder to absolute mode
            self.relativeExtrusion = False
        elif gcode == "M83":  # set extruder to relative mode
            self.relativeExtrusion = True
        elif gcode is not None and gcode.startswith("T"):  # select tool
            t = self._get_int(cmd, self.regexT)
            if t is not None:
                self.currentTool = t
                if len(self.lastExtrusion) <= self.currentTool:
                    for i in range(len(self.lastExtrusion), self.currentTool + 1):
                        self.lastExtrusion.append(0.0)
                        self.totalExtrusion.append(0.0)
                        self.maxExtrusion.append(0.0)
        elif gcode.startswith("M200"):  # volumetric extrusion
            t = self._get_int(cmd, self.regexT, "search")
            if t is not None:
                if len(self.volumetricExtrusion) <= t:
                    for i in xrange(len(self.volumetricExtrusion), t + 1):
                        self.volumetricExtrusion.append(False)
                        self.filamentDiametersByM200.append(1.75)
                        self._baseAreas.append(self._calc_base_area(1.75))
            else:
                t = self.currentTool
            d = self._get_float(cmd, self.regexD, "search")
            if d is not None and d > 0:
                self.volumetricExtrusion[t] = True
                self.filamentDiametersByM200[t] = d
                self._baseAreas[t] = self._calc_base_area(d)
            else:
                self.volumetricExtrusion[t] = False
        else:
            # Unhandled/unrecognized gcode command
            return False

        return True

    def set_g90_extruder(self, flag):
        self.g90_extruder = flag

    def get_extrusion(self):
        return self.maxExtrusion

    def get_current_tool(self):
        return self.currentTool

    def _get_int(self, cmd, regex, match_type="match"):
        result = regex.search(cmd) if match_type == "search" else regex.match(cmd)
        if result is not None:
            return int(result.group(1))
        else:
            return None

    def _get_float(self, cmd, regex, match_type="match"):
        result = regex.search(cmd) if match_type == "search" else regex.match(cmd)
        if result is not None:
            return float(result.group(1))
        else:
            return None

    def _calc_base_area(self, d):
        return math.pi * (d/2)**2
