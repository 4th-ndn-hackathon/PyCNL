# -*- Mode:python; c-file-style:"gnu"; indent-tabs-mode:nil -*- */
#
# Copyright (C) 2017 Regents of the University of California.
# Author: Jeff Thompson <jefft0@remap.ucla.edu>
#
# This program is free software: you can redistribute it and/or modify
# it under the terms of the GNU Lesser General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU Lesser General Public License for more details.
#
# You should have received a copy of the GNU Lesser General Public License
# along with this program.  If not, see <http://www.gnu.org/licenses/>.
# A copy of the GNU Lesser General Public License is in the file COPYING.

"""
This module defines the NameSynceHandler class which uses ChronoSync to run
the NameSync protocol to add announced names to a NameSpace object.
"""

import logging
from pyndn.sync import ChronoSync2013

class NameSyncHandler(object):
    """
    Create a NameSynceHandler object to attach to the given Namespace. This
    holds an internal ChronoSync2013 with the given values. This uses the Face
    which must already be set for the Namespace (or one of its parents).
    """
    def __init__(self, namespace):
        face = namespace._getFace()
